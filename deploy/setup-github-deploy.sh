#!/usr/bin/env bash
# GitHub Actions → production deploy-ийн AWS талын НЭГ УДААГИЙН тохиргоо (идемпотент).
# Локал дээрээс, AWS admin эрхтэйгээр ажиллуулна:   bash deploy/setup-github-deploy.sh
#
# Юу үүсгэх вэ (бүгд үнэгүй — IAM, SSM Run Command төлбөргүй):
#   1. GitHub OIDC provider (token.actions.githubusercontent.com)
#   2. EC2-д SSM эрх: role + instance profile `edu-union-ec2-ssm` (AmazonSSMManagedInstanceCore)
#      — инстанс аль хэдийн profile-тэй бол тэр role-д л policy-г залгана
#   3. GitHub-ийн deploy role `edu-union-github-deploy` — ЗӨВХӨН энэ repo-ийн `production`
#      environment assume хийнэ; эрх нь ЗӨВХӨН энэ инстанс дээр AWS-RunShellScript ажиллуулах
#   4. repo variable AWS_DEPLOY_ROLE_ARN (gh CLI байвал автоматаар, эс бол гараар)
set -euo pipefail

REGION="${REGION:-ap-northeast-1}"
REPO="${REPO:-baigalaaZorigt/edu-union-backend}"
INSTANCE_ID="${INSTANCE_ID:-i-03648c2bcc4e19350}"
EC2_ROLE=edu-union-ec2-ssm
DEPLOY_ROLE=edu-union-github-deploy
OIDC_HOST=token.actions.githubusercontent.com

aws() { command aws --region "$REGION" "$@"; }
say() { echo; echo "==> $*"; }

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
OIDC_ARN="arn:aws:iam::${ACCOUNT}:oidc-provider/${OIDC_HOST}"
say "Account $ACCOUNT | Бүс $REGION | Repo $REPO | Инстанс $INSTANCE_ID"

say "1/4 GitHub OIDC provider"
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1; then
  echo "байна"
else
  aws iam create-open-id-connect-provider --url "https://${OIDC_HOST}" \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 >/dev/null
  echo "үүслээ"
fi

say "2/4 EC2 → SSM эрх"
ASSOC="$(aws ec2 describe-iam-instance-profile-associations \
  --filters "Name=instance-id,Values=$INSTANCE_ID" "Name=state,Values=associated" \
  --query 'IamInstanceProfileAssociations[0].IamInstanceProfile.Arn' --output text)"
if [ "$ASSOC" != "None" ]; then
  PROFILE="${ASSOC##*/}"
  ROLE_ON_PROFILE="$(aws iam get-instance-profile --instance-profile-name "$PROFILE" \
    --query 'InstanceProfile.Roles[0].RoleName' --output text)"
  echo "инстанс аль хэдийн '$PROFILE' profile-тэй → '$ROLE_ON_PROFILE' role-д SSM policy залгана"
  aws iam attach-role-policy --role-name "$ROLE_ON_PROFILE" \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
else
  if ! aws iam get-role --role-name "$EC2_ROLE" >/dev/null 2>&1; then
    aws iam create-role --role-name "$EC2_ROLE" --assume-role-policy-document '{
      "Version":"2012-10-17","Statement":[{"Effect":"Allow",
      "Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  fi
  aws iam attach-role-policy --role-name "$EC2_ROLE" \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
  if ! aws iam get-instance-profile --instance-profile-name "$EC2_ROLE" >/dev/null 2>&1; then
    aws iam create-instance-profile --instance-profile-name "$EC2_ROLE" >/dev/null
    aws iam add-role-to-instance-profile --instance-profile-name "$EC2_ROLE" --role-name "$EC2_ROLE"
    sleep 10                                   # IAM тархах хугацаа
  fi
  aws ec2 associate-iam-instance-profile --instance-id "$INSTANCE_ID" \
    --iam-instance-profile "Name=$EC2_ROLE" >/dev/null
  echo "'$EC2_ROLE' profile инстанст залгагдлаа (дахин асаах шаардлагагүй)"
fi

say "3/4 GitHub deploy role"
TRUST=$(cat <<JSON
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
 "Principal":{"Federated":"$OIDC_ARN"},"Action":"sts:AssumeRoleWithWebIdentity",
 "Condition":{"StringEquals":{"${OIDC_HOST}:aud":"sts.amazonaws.com",
   "${OIDC_HOST}:sub":"repo:${REPO}:environment:production"}}}]}
JSON
)
if aws iam get-role --role-name "$DEPLOY_ROLE" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "$DEPLOY_ROLE" --policy-document "$TRUST"
else
  aws iam create-role --role-name "$DEPLOY_ROLE" --assume-role-policy-document "$TRUST" \
    --max-session-duration 3600 >/dev/null
fi
aws iam put-role-policy --role-name "$DEPLOY_ROLE" --policy-name ssm-deploy --policy-document "$(cat <<JSON
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":"ssm:SendCommand","Resource":[
   "arn:aws:ec2:${REGION}:${ACCOUNT}:instance/${INSTANCE_ID}",
   "arn:aws:ssm:${REGION}::document/AWS-RunShellScript"]},
 {"Effect":"Allow","Action":["ssm:GetCommandInvocation","ssm:ListCommandInvocations"],"Resource":"*"}]}
JSON
)"
ROLE_ARN="$(aws iam get-role --role-name "$DEPLOY_ROLE" --query Role.Arn --output text)"
echo "$ROLE_ARN"

say "4/4 GitHub repo variable AWS_DEPLOY_ROLE_ARN"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  gh variable set AWS_DEPLOY_ROLE_ARN --repo "$REPO" --body "$ROLE_ARN"
  echo "тохирууллаа"
else
  echo "gh CLI алга — GitHub → Settings → Secrets and variables → Actions → Variables:"
  echo "  AWS_DEPLOY_ROLE_ARN = $ROLE_ARN"
fi

say "SSM бүртгэлийг хүлээж байна (агент 1-5 минутад холбогдоно)"
for _ in $(seq 1 30); do
  PING="$(aws ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
    --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null || true)"
  [ "$PING" = Online ] && { echo "SSM: Online — бэлэн"; exit 0; }
  sleep 10
done
echo "SSM одоохондоо Online биш. Хэдэн минутын дараа шалгана уу; удаан бол EC2 дээр:"
echo "  sudo systemctl restart amazon-ssm-agent"
