#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ENV_FILE="$DEPLOY_DIR/.env.middleware"
ENV_TEMPLATE="$DEPLOY_DIR/.env.middleware.example"
STUDIO_ENV_FILE="$DEPLOY_DIR/.env.studio"
STUDIO_ENV_TEMPLATE="$DEPLOY_DIR/.env.studio.example"
MIDDLEWARE_COMPOSE_FILE="$DEPLOY_DIR/docker-compose.middleware.yaml"
STUDIO_COMPOSE_FILE="$DEPLOY_DIR/docker-compose.studio.yaml"
WORKBENCH_ENV_FILE="$DEPLOY_DIR/.env.workbench"
WORKBENCH_ENV_TEMPLATE="$DEPLOY_DIR/.env.workbench.example"
WORKBENCH_COMPOSE_FILE="$DEPLOY_DIR/docker-compose.workbench.yaml"
WORKBENCH_CHECK_SCRIPT="$DEPLOY_DIR/check-workbench.sh"
COMPOSE_FILES="docker-compose.middleware.yaml"
POSTGRES_MODE=external
REDIS_MODE=external
RABBITMQ_MODE=external
STORAGE_MODE=external
SELECTED_MODE=
SELECTED_PROVIDER=
DEPLOYMENT_ACCESS_HOST=

info() {
  printf '\n==> %s\n' "$*"
}

success() {
  printf '[通过] %s\n' "$*"
}

warn() {
  printf '[注意] %s\n' "$*" >&2
}

die() {
  printf '[失败] %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}

prompt_required() {
  local variable_name="$1"
  local label="$2"
  local default_value="${3-}"
  local input_value=""

  while [[ -z "$input_value" ]]; do
    if [[ -n "$default_value" ]]; then
      read -r -p "$label [$default_value]: " input_value
      input_value="${input_value:-$default_value}"
    else
      read -r -p "$label: " input_value
    fi
    if [[ "$input_value" == *"'"* ]]; then
      warn "输入不能包含英文单引号。"
      input_value=""
    fi
  done

  printf -v "$variable_name" '%s' "$input_value"
}

prompt_port() {
  local variable_name="$1"
  local label="$2"
  local default_value="$3"
  local value=""

  while true; do
    prompt_required value "$label" "$default_value"
    if [[ "$value" =~ ^[0-9]+$ ]] && ((value >= 1 && value <= 65535)); then
      printf -v "$variable_name" '%s' "$value"
      return
    fi
    warn "端口必须是 1 到 65535 之间的整数。"
    value=""
  done
}

image_version_valid() {
  [[ "$1" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]
}

prompt_image_version() {
  local variable_name="$1"
  local label="$2"
  local default_value="$3"
  local value=""

  while true; do
    prompt_required value "$label" "$default_value"
    if image_version_valid "$value" && [[ "$value" != CHANGE_ME* ]]; then
      printf -v "$variable_name" '%s' "$value"
      return
    fi
    warn "镜像版本不是有效的 Docker tag。"
    value=""
  done
}

prompt_url() {
  local variable_name="$1"
  local label="$2"
  local default_value="${3-}"
  local value=""

  while true; do
    prompt_required value "$label" "$default_value"
    if [[ "$value" == http://* || "$value" == https://* ]]; then
      printf -v "$variable_name" '%s' "${value%/}"
      return
    fi
    warn "地址必须以 http:// 或 https:// 开头。"
    value=""
  done
}

ensure_deployment_access_host() {
  local value=""

  [[ -n "$DEPLOYMENT_ACCESS_HOST" ]] && return
  while true; do
    prompt_required value "部署服务器对外访问 IP 或域名（IPv6 使用 []，不含协议和端口）"
    if [[ "$value" != *://* && "$value" != */* && "$value" != *[[:space:]]* &&
      ( "$value" != *:* || "$value" == \[*\] ) ]]; then
      DEPLOYMENT_ACCESS_HOST="$value"
      return
    fi
    warn "请只输入 IP 或域名（IPv6 使用 []），不要包含协议、端口或路径。"
    value=""
  done
}

deployment_access_url() {
  local port="$1"
  local host="$DEPLOYMENT_ACCESS_HOST"

  printf 'http://%s:%s' "$host" "$port"
}

prompt_secret_confirm() {
  local variable_name="$1"
  local label="$2"
  local first=""
  local second=""

  while true; do
    read -r -s -p "$label: " first
    printf '\n'
    read -r -s -p "再次确认$label: " second
    printf '\n'
    if [[ -z "$first" ]]; then
      warn "密码或密钥不能为空。"
    elif [[ "$first" == *"'"* ]]; then
      warn "密码或密钥不能包含英文单引号。"
    elif [[ "$first" != "$second" ]]; then
      warn "两次输入不一致，请重新输入。"
    else
      printf -v "$variable_name" '%s' "$first"
      return
    fi
  done
}

confirm() {
  local label="$1"
  local default_answer="${2:-y}"
  local answer=""
  local hint='[Y/n]'

  [[ "$default_answer" == n ]] && hint='[y/N]'
  while true; do
    read -r -p "$label $hint: " answer
    answer="${answer:-$default_answer}"
    case "$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')" in
      y | yes) return 0 ;;
      n | no) return 1 ;;
      *) warn "请输入 y 或 n。" ;;
    esac
  done
}

choose_mode() {
  local service_name="$1"
  local choice=""

  while true; do
    printf '\n%s 部署方式：\n' "$service_name"
    printf '  1) 本地：由 Docker Compose 部署\n'
    printf '  2) 线上：连接外部服务\n'
    read -r -p '请选择 [1-2]: ' choice
    case "$choice" in
      1) SELECTED_MODE=local; return ;;
      2) SELECTED_MODE=external; return ;;
      *) warn "请输入 1 或 2。" ;;
    esac
  done
}

choose_storage_provider() {
  local choice=""

  while true; do
    printf '\n外部存储类型：\n'
    printf '  1) MinIO\n'
    printf '  2) 阿里云 OSS\n'
    printf '  3) Azure Blob\n'
    read -r -p '请选择 [1-3]: ' choice
    case "$choice" in
      1) SELECTED_PROVIDER=minio; return ;;
      2) SELECTED_PROVIDER=aliyun-oss; return ;;
      3) SELECTED_PROVIDER=azure-blob; return ;;
      *) warn "请输入 1、2 或 3。" ;;
    esac
  done
}

dotenv_encode() {
  local value="$1"
  if [[ "$value" =~ ^[A-Za-z0-9_./,:@+-]*$ ]]; then
    printf '%s' "$value"
    return
  fi
  [[ "$value" != *"'"* ]] || die "环境变量值不能包含英文单引号，请更换输入。"
  printf "'%s'" "$value"
}

set_env_in_file() {
  local target_file="$1"
  local key="$2"
  local value="$3"
  local encoded=""
  local temporary_file=""

  encoded="$(dotenv_encode "$value")"
  temporary_file="$(mktemp "${target_file}.tmp.XXXXXX")"
  BASIL_DEPLOY_ENV_KEY="$key" BASIL_DEPLOY_ENV_VALUE="$encoded" \
    awk '
      BEGIN {
        key = ENVIRON["BASIL_DEPLOY_ENV_KEY"]
        replacement = key "=" ENVIRON["BASIL_DEPLOY_ENV_VALUE"]
      }
      index($0, key "=") == 1 {
        print replacement
        found = 1
        next
      }
      { print }
      END {
        if (!found) print replacement
      }
    ' "$target_file" > "$temporary_file"
  mv "$temporary_file" "$target_file"
  chmod 600 "$target_file"
}

set_env() {
  set_env_in_file "$ENV_FILE" "$@"
}

workbench_set_env() {
  set_env_in_file "$WORKBENCH_ENV_FILE" "$@"
}

studio_set_env() {
  set_env_in_file "$STUDIO_ENV_FILE" "$@"
}

dotenv_get_from_file() {
  local target_file="$1"
  local key="$2"
  local value=""

  value="$(BASIL_DEPLOY_ENV_KEY="$key" awk '
    index($0, ENVIRON["BASIL_DEPLOY_ENV_KEY"] "=") == 1 {
      sub(/^[^=]*=/, "")
      print
      exit
    }
  ' "$target_file")"

  if [[ "$value" == \'*\' && ${#value} -ge 2 ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "$value" == \"*\" && ${#value} -ge 2 ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

dotenv_get() {
  dotenv_get_from_file "$ENV_FILE" "$1"
}

workbench_get_env() {
  dotenv_get_from_file "$WORKBENCH_ENV_FILE" "$1"
}

studio_get_env() {
  dotenv_get_from_file "$STUDIO_ENV_FILE" "$1"
}

ensure_image_version() {
  local getter="$1"
  local setter="$2"
  local key="$3"
  local label="$4"
  local resolved_version=""

  resolved_version="$("$getter" "$key")"
  if [[ -z "$resolved_version" || "$resolved_version" == CHANGE_ME* ]]; then
    prompt_image_version resolved_version "$label Docker tag" ""
    "$setter" "$key" "$resolved_version"
  fi
}

enforce_studio_cookie_mode() {
  studio_set_env ENABLE_HTTPS_COOKIES false
}

rebuild_compose_files() {
  COMPOSE_FILES="docker-compose.middleware.yaml"
  [[ "$POSTGRES_MODE" == local ]] && COMPOSE_FILES+=",compose/db.yaml"
  [[ "$REDIS_MODE" == local ]] && COMPOSE_FILES+=",compose/cache.yaml"
  [[ "$RABBITMQ_MODE" == local ]] && COMPOSE_FILES+=",compose/mq.yaml"
  [[ "$STORAGE_MODE" == local ]] && COMPOSE_FILES+=",compose/storage.yaml"
  set_env COMPOSE_FILE "$COMPOSE_FILES"
}

middleware_compose() {
  docker compose --env-file "$ENV_FILE" "$@"
}

studio_compose() {
  docker compose --env-file "$ENV_FILE" --env-file "$STUDIO_ENV_FILE" \
    -f "$STUDIO_COMPOSE_FILE" "$@"
}

prepare_owned_directory() {
  local path="$1"
  local ownership_image=""
  local ownership_platform=""
  mkdir -p "$path"

  if [[ "$(id -u)" -eq 0 ]]; then
    chown -R 1001:1001 "$path"
  elif [[ "$(uname -s)" == Darwin ]]; then
    # Docker Desktop 的目录权限在 Linux 容器中设置，避免要求 macOS sudo 密码。
    # 使用前一步已验证的本地 PostgreSQL 镜像，不因全局 amd64 模拟设置另拉一个平台。
    ownership_image="$(docker image inspect --format '{{.Id}}' \
      "$(dotenv_get POSTGRES_IMAGE):$(dotenv_get POSTGRES_VERSION)")"
    ownership_platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$ownership_image")"
    docker run --rm --pull never --platform "$ownership_platform" --user 0 --entrypoint chown \
      --volume "$path:/data" \
      "$ownership_image" -R 1001:1001 /data
  elif command -v sudo >/dev/null 2>&1; then
    sudo chown -R 1001:1001 "$path"
  else
    die "$path 需要归属 1001:1001；请使用 root 权限处理后重试。"
  fi
}

retry_configuration() {
  confirm "测试失败，是否重新配置当前服务？" y || die "部署已停止。"
}

test_postgresql_local() {
  local username="$1"
  local password="$2"
  local database="$3"
  local extension=""

  extension="$(middleware_compose exec -T -e "PGPASSWORD=$password" postgresql \
    psql --username "$username" --dbname "$database" --tuples-only --no-align \
    --command "SELECT extname FROM pg_extension WHERE extname = 'vector';")"
  [[ "$extension" == vector ]]
}

test_postgresql_external() {
  local host="$1"
  local port="$2"
  local username="$3"
  local password="$4"
  local database="$5"
  local image=""
  local extension=""

  image="$(dotenv_get POSTGRES_IMAGE):$(dotenv_get POSTGRES_VERSION)"
  ops pull "$image" || return 1
  extension="$(PGPASSWORD="$password" docker run --rm \
    --env PGPASSWORD "$image" psql \
    --host "$host" --port "$port" --username "$username" --dbname "$database" \
    --tuples-only --no-align \
    --command "SELECT extname FROM pg_extension WHERE extname = 'vector';")"
  [[ "$extension" == vector ]]
}

test_redis_local() {
  local password="$1"
  [[ "$(middleware_compose exec -T -e "REDISCLI_AUTH=$password" redis redis-cli ping)" == PONG ]]
}

test_redis_external() {
  local host="$1"
  local port="$2"
  local password="$3"
  local use_tls="$4"
  local image=""
  local output=""

  image="$(dotenv_get REDIS_IMAGE):$(dotenv_get REDIS_VERSION)"
  ops pull "$image" || return 1
  if [[ "$use_tls" == true ]]; then
    output="$(REDISCLI_AUTH="$password" docker run --rm \
      --env REDISCLI_AUTH "$image" redis-cli -h "$host" -p "$port" --tls ping)"
  else
    output="$(REDISCLI_AUTH="$password" docker run --rm \
      --env REDISCLI_AUTH "$image" redis-cli -h "$host" -p "$port" ping)"
  fi
  [[ "$output" == PONG ]]
}

test_rabbitmq_endpoint() {
  local host="$1"
  local port="$2"
  local username="$3"
  local password="$4"

  curl --fail --silent --show-error --connect-timeout 10 --max-time 20 \
    --user "$username:$password" "http://$host:$port/api/overview" >/dev/null 2>&1 ||
    curl --fail --silent --show-error --connect-timeout 10 --max-time 20 \
      --user "$username:$password" "https://$host:$port/api/overview" >/dev/null 2>&1
}

test_url_reachable() {
  local url="$1"
  local status=""

  status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --connect-timeout 10 --max-time 20 "$url")" || return 1
  [[ "$status" != 000 ]]
}

clear_minio_config() {
  set_env MINIO_EXPOSE_URL ""
  set_env MINIO_HOST ""
  set_env MINIO_USERNAME ""
  set_env MINIO_PASSWORD ""
}

clear_aliyun_oss_config() {
  set_env ALI_OSS_ACCESS_ID ""
  set_env ALI_OSS_ACCESS_KEY ""
  set_env ALI_OSS_ENDPOINT ""
  studio_set_env ALI_OSS_BUCKET_NAME ""
}

clear_azure_blob_config() {
  set_env AZURE_BLOB_ACCOUNT_NAME ""
  set_env AZURE_BLOB_ACCOUNT_KEY ""
  set_env AZURE_BLOB_ENDPOINT ""
  studio_set_env AZURE_BLOB_CONTAINER ""
}

initialize_postgresql() {
  reuse_middleware postgresql && return 0
  local host=""
  local port=""
  local username=""
  local password=""
  local database=""

  info "1/4 初始化 PostgreSQL"
  while true; do
    choose_mode PostgreSQL
    if [[ "$SELECTED_MODE" == local ]]; then
      ensure_image_version dotenv_get set_env POSTGRES_VERSION PostgreSQL
      prompt_required username "数据库用户名" basilos
      prompt_secret_confirm password "数据库密码"
      database=basilos

      POSTGRES_MODE=local
      set_env POSTGRESQL_HOST postgresql
      set_env POSTGRESQL_PORT 5432
      set_env POSTGRESQL_USERNAME "$username"
      set_env POSTGRESQL_PASSWORD "$password"
      set_env POSTGRESQL_BOOTSTRAP_DATABASE "$database"
      studio_set_env POSTGRESQL_DATABASE "$database"
      rebuild_compose_files

      mkdir -p "$DEPLOY_DIR/data/postgresql"
      if ops up middleware postgresql &&
        middleware_compose run --rm postgresql-init &&
        test_postgresql_local "$username" "$password" "$database"; then
        success "本地 PostgreSQL 已部署，连接正常，vector 扩展可用。"
        return
      fi
    else
      prompt_required host "PostgreSQL 地址"
      prompt_port port "PostgreSQL 端口" 5432
      prompt_required database "数据库名称" basilos
      prompt_required username "数据库用户名" basilos
      prompt_secret_confirm password "数据库密码"

      POSTGRES_MODE=external
      set_env POSTGRESQL_HOST "$host"
      set_env POSTGRESQL_PORT "$port"
      set_env POSTGRESQL_USERNAME "$username"
      set_env POSTGRESQL_PASSWORD "$password"
      set_env POSTGRESQL_BOOTSTRAP_DATABASE "$database"
      studio_set_env POSTGRESQL_DATABASE "$database"
      rebuild_compose_files

      if test_postgresql_external "$host" "$port" "$username" "$password" "$database"; then
        success "外部 PostgreSQL 连接正常，vector 扩展可用。"
        return
      fi
    fi
    retry_configuration
  done
}

initialize_redis() {
  reuse_middleware redis && return 0
  local host=""
  local port=""
  local password=""
  local database=""
  local use_tls=false

  info "2/4 初始化 Redis"
  while true; do
    choose_mode Redis
    if [[ "$SELECTED_MODE" == local ]]; then
      ensure_image_version dotenv_get set_env REDIS_VERSION Redis
      prompt_secret_confirm password "Redis 密码"

      REDIS_MODE=local
      set_env REDIS_HOST redis
      set_env REDIS_PORT 6379
      set_env REDIS_PASSWORD "$password"
      studio_set_env REDIS_DATABASE 0
      set_env REDIS_SSL false
      rebuild_compose_files

      prepare_owned_directory "$DEPLOY_DIR/data/redis"
      if ops up middleware redis && test_redis_local "$password"; then
        success "本地 Redis 已部署并通过连接测试。"
        return
      fi
    else
      prompt_required host "Redis 地址"
      prompt_port port "Redis 端口" 6379
      prompt_secret_confirm password "Redis 密码"
      prompt_required database "Redis 数据库编号" 0
      if confirm "Redis 是否启用 TLS？" n; then use_tls=true; else use_tls=false; fi

      REDIS_MODE=external
      set_env REDIS_HOST "$host"
      set_env REDIS_PORT "$port"
      set_env REDIS_PASSWORD "$password"
      studio_set_env REDIS_DATABASE "$database"
      set_env REDIS_SSL "$use_tls"
      rebuild_compose_files

      if test_redis_external "$host" "$port" "$password" "$use_tls"; then
        success "外部 Redis 连接正常。"
        return
      fi
    fi
    retry_configuration
  done
}

initialize_rabbitmq() {
  reuse_middleware rabbitmq && return 0
  local host=""
  local port=""
  local management_port=""
  local username=""
  local password=""
  local virtual_host=""
  local local_management_port=""

  info "3/4 初始化 RabbitMQ"
  while true; do
    choose_mode RabbitMQ
    if [[ "$SELECTED_MODE" == local ]]; then
      ensure_image_version dotenv_get set_env RABBITMQ_VERSION RabbitMQ
      prompt_required username "RabbitMQ 用户名" basilos
      prompt_secret_confirm password "RabbitMQ 密码"

      RABBITMQ_MODE=local
      set_env RABBITMQ_HOST rabbitmq
      set_env RABBITMQ_PORT 5672
      set_env RABBITMQ_MANAGEMENT_PORT 15672
      set_env RABBITMQ_USERNAME "$username"
      set_env RABBITMQ_PASSWORD "$password"
      set_env RABBITMQ_VIRTUAL_HOST /basilos
      rebuild_compose_files

      mkdir -p "$DEPLOY_DIR/data/rabbitmq"
      local_management_port="$(dotenv_get RABBITMQ_MANAGEMENT_HOST_PORT)"
      if ops up middleware rabbitmq &&
        test_rabbitmq_endpoint 127.0.0.1 "$(dotenv_get RABBITMQ_MANAGEMENT_HOST_PORT)" "$username" "$password"; then
        success "本地 RabbitMQ 已部署并通过连接测试。"
        return
      fi
    else
      prompt_required host "RabbitMQ 地址"
      prompt_port port "RabbitMQ 端口" 5672
      prompt_port management_port "RabbitMQ 管理端口" 15672
      prompt_required username "RabbitMQ 用户名" basilos
      prompt_secret_confirm password "RabbitMQ 密码"
      prompt_required virtual_host "RabbitMQ Virtual Host" /basilos

      RABBITMQ_MODE=external
      set_env RABBITMQ_HOST "$host"
      set_env RABBITMQ_PORT "$port"
      set_env RABBITMQ_MANAGEMENT_PORT "$management_port"
      set_env RABBITMQ_USERNAME "$username"
      set_env RABBITMQ_PASSWORD "$password"
      set_env RABBITMQ_VIRTUAL_HOST "$virtual_host"
      rebuild_compose_files

      if test_rabbitmq_endpoint "$host" "$management_port" "$username" "$password"; then
        success "外部 RabbitMQ 管理接口连接正常。"
        return
      fi
    fi
    retry_configuration
  done
}

configure_local_minio() {
  local username=""
  local password=""
  local expose_url=""
  local expose_port=""

  ensure_image_version dotenv_get set_env MINIO_VERSION MinIO
  prompt_required username "MinIO 用户名" basilos
  prompt_secret_confirm password "MinIO 密码"
  ensure_deployment_access_host
  expose_port="$(dotenv_get MINIO_API_HOST_PORT)"
  info "MinIO API 当前 Compose 对外端口：${expose_port}；使用 HTTPS 或反向代理时请覆盖默认值。"
  prompt_url expose_url "AI 模型可访问的 MinIO 地址" "$(deployment_access_url "$expose_port")"

  STORAGE_MODE=local
  set_env FILE_SERVICE_SELECTOR minio
  studio_set_env FILE_SERVICE_PRIVATE_BUCKET_NAME studio-private
  studio_set_env FILE_SERVICE_PUBLIC_BUCKET_NAME studio-public
  set_env MINIO_EXPOSE_URL "$expose_url"
  set_env MINIO_HOST minio
  set_env MINIO_PORT 9000
  set_env MINIO_USERNAME "$username"
  set_env MINIO_PASSWORD "$password"
  clear_aliyun_oss_config
  clear_azure_blob_config
  rebuild_compose_files

  prepare_owned_directory "$DEPLOY_DIR/data/minio"
  ops up middleware minio &&
    middleware_compose exec -T minio curl --fail --silent http://127.0.0.1:9000/minio/health/ready >/dev/null &&
    test_url_reachable "$(dotenv_get MINIO_EXPOSE_URL)/minio/health/ready"
}

configure_external_minio() {
  local host=""
  local port=""
  local username=""
  local password=""
  local expose_url=""

  prompt_required host "MinIO 地址（不含协议）"
  prompt_port port "MinIO API 端口" 9000
  prompt_required username "MinIO 用户名"
  prompt_secret_confirm password "MinIO 密码"
  prompt_url expose_url "AI 模型可访问的 MinIO 地址" "http://$host:$port"

  STORAGE_MODE=external
  set_env FILE_SERVICE_SELECTOR minio
  studio_set_env FILE_SERVICE_PRIVATE_BUCKET_NAME studio-private
  studio_set_env FILE_SERVICE_PUBLIC_BUCKET_NAME studio-public
  set_env MINIO_EXPOSE_URL "$expose_url"
  set_env MINIO_HOST "$host"
  set_env MINIO_PORT "$port"
  set_env MINIO_USERNAME "$username"
  set_env MINIO_PASSWORD "$password"
  clear_aliyun_oss_config
  clear_azure_blob_config
  rebuild_compose_files

  test_url_reachable "$expose_url/minio/health/ready"
}

configure_aliyun_oss() {
  local access_id=""
  local access_key=""
  local endpoint=""
  local bucket=""

  prompt_required access_id "OSS AccessKey ID"
  prompt_secret_confirm access_key "OSS AccessKey Secret"
  prompt_url endpoint "OSS Endpoint"
  prompt_required bucket "OSS Bucket 名称" studio

  STORAGE_MODE=external
  set_env FILE_SERVICE_SELECTOR aliyun-oss
  studio_set_env FILE_SERVICE_PRIVATE_BUCKET_NAME studio-private
  studio_set_env FILE_SERVICE_PUBLIC_BUCKET_NAME studio-public
  set_env ALI_OSS_ACCESS_ID "$access_id"
  set_env ALI_OSS_ACCESS_KEY "$access_key"
  set_env ALI_OSS_ENDPOINT "$endpoint"
  studio_set_env ALI_OSS_BUCKET_NAME "$bucket"
  clear_minio_config
  clear_azure_blob_config
  rebuild_compose_files

  test_url_reachable "$endpoint/$bucket"
}

configure_azure_blob() {
  local account_name=""
  local account_key=""
  local endpoint=""
  local container=""

  prompt_required account_name "Azure Storage 账户名称"
  prompt_secret_confirm account_key "Azure Storage 账户密钥"
  prompt_url endpoint "Azure Blob Endpoint"
  prompt_required container "Azure Blob Container" studio

  STORAGE_MODE=external
  set_env FILE_SERVICE_SELECTOR azure-blob
  studio_set_env FILE_SERVICE_PRIVATE_BUCKET_NAME studio-private
  studio_set_env FILE_SERVICE_PUBLIC_BUCKET_NAME studio-public
  set_env AZURE_BLOB_ACCOUNT_NAME "$account_name"
  set_env AZURE_BLOB_ACCOUNT_KEY "$account_key"
  set_env AZURE_BLOB_ENDPOINT "$endpoint"
  studio_set_env AZURE_BLOB_CONTAINER "$container"
  clear_minio_config
  clear_aliyun_oss_config
  rebuild_compose_files

  test_url_reachable "$endpoint/$container"
}

initialize_storage() {
  reuse_middleware storage && return 0
  info "4/4 初始化对象存储"
  while true; do
    choose_mode "对象存储"
    if [[ "$SELECTED_MODE" == local ]]; then
      if configure_local_minio; then
        success "本地 MinIO 已部署，内部和公开地址均可访问。"
        break
      fi
    else
      choose_storage_provider
      case "$SELECTED_PROVIDER" in
        minio) configure_external_minio && break ;;
        aliyun-oss) configure_aliyun_oss && break ;;
        azure-blob) configure_azure_blob && break ;;
      esac
    fi
    retry_configuration
  done

  success "对象存储地址可从当前服务器访问。"
  warn "AI 打标还要求实际使用的 AI 模型能够访问对象存储生成的文件地址，请从模型所在网络完成验证。"
}

ensure_studio_configuration() {
  local encryptor_password=""
  local assets_search_url=""
  local studio_frontend_url=""
  local studio_frontend_port=""
  local assets_path='/basilos/asset/search-embed'

  ensure_image_version studio_get_env studio_set_env STUDIO_VERSION "Studio API"
  ensure_image_version studio_get_env studio_set_env STUDIO_FRONTEND_VERSION "Studio Frontend"
  ensure_image_version studio_get_env studio_set_env NODE_SANDBOX_VERSION "Studio Node Sandbox"

  encryptor_password="$(studio_get_env ENCRYPTOR_PASSWORD)"
  if [[ -z "$encryptor_password" || "$encryptor_password" == CHANGE_ME_* ]]; then
    prompt_secret_confirm encryptor_password "Studio 数据加密密码"
    studio_set_env ENCRYPTOR_PASSWORD "$encryptor_password"
  fi

  assets_search_url="$(studio_get_env ASSETS_SEARCH_SNAPSHOT_URL)"
  if [[ -n "$assets_search_url" &&
    "$assets_search_url" != *CHANGE_ME* &&
    "$assets_search_url" == *"$assets_path" ]]; then
    studio_frontend_url="${assets_search_url%$assets_path}"
  else
    ensure_deployment_access_host
    studio_frontend_port="$(studio_get_env STUDIO_FRONTEND_HOST_PORT)"
    info "Studio Frontend 当前 Compose 对外端口：${studio_frontend_port}；使用 HTTPS 或反向代理时请覆盖默认值。"
    prompt_url studio_frontend_url "Studio 前端访问地址" "$(deployment_access_url "$studio_frontend_port")"
  fi
  studio_set_env ASSETS_SEARCH_SNAPSHOT_URL "${studio_frontend_url%/}$assets_path"
  studio_set_env VIEW_SNAPSHOT_URL "${studio_frontend_url%/}/basilos/studio/engine/multi-dim-table-embed"
}

deploy_studio() {
  local studio_frontend_url=""

  info "部署 Basil Studio"
  enforce_studio_cookie_mode
  ensure_studio_configuration
  mkdir -p "$DEPLOY_DIR/data/studio-logs"
  studio_compose config --quiet
  ops up studio
  studio_compose ps
  studio_frontend_url="$(studio_get_env ASSETS_SEARCH_SNAPSHOT_URL)"
  studio_frontend_url="${studio_frontend_url%/basilos/asset/search-embed}"
  success "Basil Studio 容器已启动，访问地址：$studio_frontend_url"
  info "仍需按部署文档检查后端迁移、HTTP 重定向、登录和业务功能；running 不代表应用已就绪。"
}

workbench_compose() {
  docker compose --env-file "$ENV_FILE" --env-file "$WORKBENCH_ENV_FILE" \
    -f "$WORKBENCH_COMPOSE_FILE" "$@"
}

workbench_value_needs_configuration() {
  local value="$1"
  [[ -z "$value" || "$value" == *CHANGE_ME* ]]
}

generate_secret() {
  od -An -N32 -tx1 /dev/urandom | tr -d '[:space:]'
}

parse_url() {
  local url="$1"
  local remainder=""

  URL_SCHEME="${url%%://*}"
  remainder="${url#*://}"
  URL_AUTHORITY="${remainder%%/*}"
  URL_HOST="$URL_AUTHORITY"
  URL_PORT=""

  [[ "$URL_SCHEME" == http || "$URL_SCHEME" == https ]] || return 1
  [[ -n "$URL_AUTHORITY" ]] || return 1

  if [[ "$URL_AUTHORITY" == \[*\]:* ]]; then
    URL_HOST="${URL_AUTHORITY%%]:*}]"
    URL_PORT="${URL_AUTHORITY##*:}"
  elif [[ "$URL_AUTHORITY" == *:* ]]; then
    URL_HOST="${URL_AUTHORITY%%:*}"
    URL_PORT="${URL_AUTHORITY##*:}"
  fi

  if [[ -z "$URL_PORT" ]]; then
    [[ "$URL_SCHEME" == https ]] && URL_PORT=443 || URL_PORT=80
  fi
  [[ "$URL_PORT" =~ ^[0-9]+$ ]] && ((URL_PORT >= 1 && URL_PORT <= 65535))
}

ensure_workbench_url() {
  local key="$1"
  local label="$2"
  local port="$3"
  local configured_url=""
  local default_url=""

  configured_url="$(workbench_get_env "$key")"
  if workbench_value_needs_configuration "$configured_url"; then
    ensure_deployment_access_host
    default_url="$(deployment_access_url "$port")"
  elif ! parse_url "$configured_url"; then
    warn "$label 当前值无效：$configured_url"
    ensure_deployment_access_host
    default_url="$(deployment_access_url "$port")"
  fi

  if [[ -n "$default_url" ]]; then
    info "$label 当前 Compose 对外端口：${port}；使用 HTTPS 或反向代理时请覆盖默认值。"
    prompt_url configured_url "$label" "$default_url"
    workbench_set_env "$key" "$configured_url"
  fi
  WORKBENCH_VALUE="$configured_url"
}

ensure_workbench_text() {
  local key="$1"
  local label="$2"
  local default_value="${3-}"
  local value=""

  value="$(workbench_get_env "$key")"
  if workbench_value_needs_configuration "$value"; then
    prompt_required value "$label" "$default_value"
    workbench_set_env "$key" "$value"
  fi
}

ensure_workbench_generated_secret() {
  local key="$1"
  local value=""

  value="$(workbench_get_env "$key")"
  if workbench_value_needs_configuration "$value"; then
    workbench_set_env "$key" "$(generate_secret)"
    info "已生成 Workbench 密钥：$key"
  fi
}

prepare_workbench_env() {
  [[ -f "$WORKBENCH_COMPOSE_FILE" ]] || die "缺少 docker-compose.workbench.yaml"
  [[ -f "$WORKBENCH_ENV_TEMPLATE" ]] || die "缺少 .env.workbench.example"
  [[ -f "$WORKBENCH_CHECK_SCRIPT" ]] || die "缺少 check-workbench.sh"
  [[ -f "$DEPLOY_DIR/workbench/storage/nginx/runtime-nginx.conf" ]] || die "缺少 workbench/storage/nginx/runtime-nginx.conf"
  [[ -f "$DEPLOY_DIR/workbench/storage/templates/AGENTS.md" && -r "$DEPLOY_DIR/workbench/storage/templates/AGENTS.md" && ! -L "$DEPLOY_DIR/workbench/storage/templates/AGENTS.md" ]] || die "缺少可读的普通文件 workbench/storage/templates/AGENTS.md（不允许符号链接）"

  [[ ! -L "$WORKBENCH_ENV_FILE" ]] || die "拒绝修改符号链接环境文件：$WORKBENCH_ENV_FILE"
  if [[ ! -f "$WORKBENCH_ENV_FILE" ]]; then
    cp "$WORKBENCH_ENV_TEMPLATE" "$WORKBENCH_ENV_FILE"
    info "已创建 $WORKBENCH_ENV_FILE"
  fi
  chmod 600 "$WORKBENCH_ENV_FILE"
}

sync_workbench_shared_configuration() {
  local studio_vhost=""
  local storage_url=""

  studio_vhost="$(dotenv_get RABBITMQ_VIRTUAL_HOST)"
  storage_url="$(dotenv_get MINIO_EXPOSE_URL)"
  parse_url "$storage_url" || die "MINIO_EXPOSE_URL 不是有效的 HTTP(S) 地址：$storage_url"

  workbench_set_env WORKBENCH_DEPLOYMENT_ROOT "$DEPLOY_DIR"
  workbench_set_env REDIS_DATABASE 1
  workbench_set_env RABBITMQ_VIRTUAL_HOST "/${studio_vhost}"
  workbench_set_env MINIO_PUBLIC_BASE_URL "$storage_url"
  workbench_set_env MINIO_PRESIGN_ENDPOINT "$URL_HOST"
  workbench_set_env MINIO_PRESIGN_PORT "$URL_PORT"
  [[ "$URL_SCHEME" == https ]] &&
    workbench_set_env MINIO_PRESIGN_USE_SSL true ||
    workbench_set_env MINIO_PRESIGN_USE_SSL false
}

ensure_workbench_gateway() {
  local gateway_url=""
  # 平台网关代理 Studio 页面/API，不能从 Workbench 自身 API 地址推导。
  gateway_url="$(workbench_get_env BASILOS_GATEWAY_HOST)"
  if workbench_value_needs_configuration "$gateway_url"; then
    prompt_url gateway_url "Studio 平台网关地址（须从 Workbench Frontend 容器可达）"
  fi
  parse_url "$gateway_url" || die "Studio 平台网关地址无效：$gateway_url"
  workbench_set_env BASILOS_GATEWAY_HOST "${gateway_url%/}/"
}

configure_workbench() {
  local api_url=""
  local frontend_url=""
  local admin_password=""
  local api_port=""
  local frontend_port=""

  sync_workbench_shared_configuration
  ensure_image_version workbench_get_env workbench_set_env WORKBENCH_VERSION "Workbench API"
  ensure_image_version workbench_get_env workbench_set_env WORKBENCH_FRONTEND_VERSION "Workbench Frontend"
  ensure_image_version workbench_get_env workbench_set_env RUNTIME_VERSION "Workbench Runtime"
  ensure_image_version workbench_get_env workbench_set_env RUNTIME_SANDBOX_VERSION "Runtime Sandbox"
  ensure_image_version workbench_get_env workbench_set_env RUNTIME_NGINX_VERSION "Runtime Gateway"

  api_port="$(workbench_get_env WORKBENCH_HOST_PORT)"
  frontend_port="$(workbench_get_env WORKBENCH_FRONTEND_HOST_PORT)"

  ensure_workbench_url APP_URL "Workbench API 的浏览器入口（通常与前端同源）" "$frontend_port"
  api_url="$WORKBENCH_VALUE"
  parse_url "$api_url" || die "Workbench API 访问地址无效：$api_url"
  workbench_set_env BASILCRAW_API_HOST "$URL_AUTHORITY"

  ensure_workbench_gateway

  ensure_workbench_url FRONTEND_URL "Workbench 前端访问地址" "$frontend_port"
  frontend_url="$WORKBENCH_VALUE"
  workbench_set_env FRONTEND_OAUTH_RESULT_URL "$frontend_url"

  ensure_workbench_generated_secret JWT_SECRET
  ensure_workbench_generated_secret ENCRYPTION_KEY
  ensure_workbench_generated_secret RUNTIME_HTTP_SERVICE_TOKEN
  ensure_workbench_generated_secret RUNTIME_TO_WORKBENCH_SERVICE_TOKEN

  admin_password="$(workbench_get_env DEFAULT_USER_PASSWORD)"
  if workbench_value_needs_configuration "$admin_password"; then
    prompt_secret_confirm admin_password "Workbench 新建/重置用户默认密码"
    workbench_set_env DEFAULT_USER_PASSWORD "$admin_password"
  fi
  ensure_workbench_text RUNTIME_SANDBOX_HOST_ID "Sandbox Host 稳定标识"
}

check_workbench_placeholders() {
  local keys=""

  keys="$(awk -F= '
    /^[[:space:]]*#/ || !index($0, "=") { next }
    index(substr($0, index($0, "=") + 1), "CHANGE_ME") { print $1 }
  ' "$WORKBENCH_ENV_FILE")"
  if [[ -n "$keys" ]]; then
    warn "Workbench 仍有未配置变量：$(printf '%s\n' "$keys" | tr '\n' ' ')"
    return 1
  fi
}

wait_for_url() {
  local url="$1"
  local attempt=0

  for ((attempt = 1; attempt <= 30; attempt++)); do
    if curl --fail --silent --connect-timeout 5 --max-time 10 "$url" >/dev/null; then
      return
    fi
    sleep 2
  done
  curl --fail --silent --show-error --connect-timeout 5 --max-time 10 "$url" >/dev/null
}

test_workbench_http() {
  local runtime_port=""
  local api_port=""
  local frontend_port=""

  runtime_port="$(workbench_get_env RUNTIME_GATEWAY_HOST_PORT)"
  api_port="$(workbench_get_env WORKBENCH_HOST_PORT)"
  frontend_port="$(workbench_get_env WORKBENCH_FRONTEND_HOST_PORT)"
  wait_for_url "http://127.0.0.1:$runtime_port/health" || return 1
  wait_for_url "http://127.0.0.1:$runtime_port/ready" || return 1
  wait_for_url "http://127.0.0.1:$api_port/" || return 1
  wait_for_url "http://127.0.0.1:$frontend_port/" || return 1
}

workbench_storage_supported() {
  [[ "$(dotenv_get FILE_SERVICE_SELECTOR)" == minio ]]
}

deploy_workbench() {
  local middleware_network=""
  local sandbox_image=""

  info "部署 Basil Workbench"
  if ! workbench_storage_supported; then
    warn "当前 Workbench 部署模板仅支持 MinIO 对象存储。"
    return 1
  fi

  require_command od
  prepare_workbench_env
  configure_workbench
  ENV_FILE="$WORKBENCH_ENV_FILE" bash "$WORKBENCH_CHECK_SCRIPT"
  check_workbench_placeholders || return 1

  middleware_network="$(dotenv_get BASIL_NETWORK_NAME)"
  docker network inspect "$middleware_network" >/dev/null ||
    die "Workbench 依赖的 Docker 网络不存在：$middleware_network"
  workbench_compose config --quiet

  sandbox_image="$(workbench_get_env RUNTIME_SANDBOX_IMAGE):$(workbench_get_env RUNTIME_SANDBOX_VERSION)"
  if ! docker image inspect "$sandbox_image" >/dev/null 2>&1; then
    ops pull "$sandbox_image"
  fi
  ops up workbench
  if ! test_workbench_http; then
    workbench_compose ps
    die "Workbench 基础 HTTP 检查失败，请查看容器状态和日志。"
  fi
  workbench_compose ps
  success "Basil Workbench 部署完成并通过基础 HTTP 检查。"
  info "Workbench 前端访问地址：$(workbench_get_env FRONTEND_URL)"
  info "Workbench API 访问地址：$(workbench_get_env APP_URL)"
}

deploy_all() {
  if ! workbench_storage_supported; then
    warn "一键部署需要使用 MinIO；当前未执行 Studio 或 Workbench 部署。"
    return 1
  fi
  deploy_studio
  deploy_workbench
}

prepare_deployment() {
  prepare
  info "初始化中间件"
  initialize_postgresql
  initialize_redis
  initialize_rabbitmq
  initialize_storage
}

ensure_shared_network() {
  local network_name=""

  network_name="$(dotenv_get BASIL_NETWORK_NAME)"
  [[ -n "$network_name" ]] || die "BASIL_NETWORK_NAME 不能为空。"
  if ! docker network inspect "$network_name" >/dev/null 2>&1; then
    docker network create "$network_name" >/dev/null
    info "已创建共享网络：$network_name"
  fi
}

update_service_version() {
  local label="$1"
  local getter="$2"
  local setter="$3"
  local compose_command="$4"
  local image_key="$5"
  local version_key="$6"
  local service="$7"
  local wait_timeout="$8"
  local confirm_default="$9"
  local env_file="${10}"
  local current_version=""
  local new_version=""
  local image=""
  local container_ids=""
  local previous_override=""
  local previous_override_was_set=false
  local pull_succeeded=false
  local backup_file=""
  local safe_current_version=""

  container_ids="$("$compose_command" ps -a -q "$service" 2>/dev/null || true)"
  if [[ -z "$container_ids" ]]; then
    warn "$label 未由当前 Docker Compose 部署，无法通过此脚本更新。"
    return
  fi

  image="$("$getter" "$image_key")"
  current_version="$("$getter" "$version_key")"
  prompt_image_version new_version "$label Docker tag" "$current_version"
  printf '%s: %s:%s -> %s:%s\n' "$label" "$image" "$current_version" "$image" "$new_version"
  confirm "确认更新 ${label}？" "$confirm_default" || return

  if [[ "${!version_key+x}" == x ]]; then
    previous_override_was_set=true
    previous_override="${!version_key}"
  fi
  printf -v "$version_key" '%s' "$new_version"
  export "$version_key"
  if "$compose_command" config --quiet && ops pull "$image:$new_version" --force; then
    pull_succeeded=true
  fi
  if [[ "$previous_override_was_set" == true ]]; then
    printf -v "$version_key" '%s' "$previous_override"
    export "$version_key"
  else
    unset "$version_key"
  fi
  if [[ "$pull_succeeded" != true ]]; then
    warn "$label 镜像拉取失败；环境变量和现有容器均未修改。"
    return 1
  fi

  safe_current_version="${current_version//[^A-Za-z0-9_.-]/_}"
  backup_file="${env_file}.bak.update-${service}-${safe_current_version}-$(date -u +%Y%m%dT%H%M%SZ)"
  [[ ! -e "$backup_file" ]] || die "备份文件已存在：$backup_file"
  cp -a -- "$env_file" "$backup_file"
  info "已备份环境文件：$backup_file"

  "$setter" "$version_key" "$new_version"
  if "$compose_command" config --quiet &&
    compose_recreate "$compose_command" "$service"; then
    "$compose_command" ps "$service"
    success "$label 已更新到 ${new_version}。"
    return
  fi

  cp -a -- "$backup_file" "$env_file"
  warn "$label 更新失败，正在使用备份恢复 ${current_version}。"
  if "$compose_command" config --quiet &&
    compose_recreate "$compose_command" "$service"; then
    "$compose_command" ps "$service"
    warn "$label 已恢复到 ${current_version}；数据库迁移和外部副作用不会随镜像自动回滚。"
  else
    warn "$label 自动恢复失败；环境文件已恢复，请立即检查容器和日志。"
  fi
  return 1
}

update_runtime_sandbox_image() {
  local image="" current_version="" new_version="" backup_file=""
  local safe_current_version="" container_id="" configured_image=""

  container_id="$(workbench_compose ps -a -q workbench-runtime-node)" || return 1
  [[ -n "$container_id" ]] || { warn "Runtime 尚未部署，无法更新 Sandbox 配置。"; return 1; }
  # Shell 环境变量优先于 env 文件，避免文件更新后仍使用外部旧值。
  [[ -z "${RUNTIME_SANDBOX_VERSION+x}" ]] || {
    warn "请先 unset RUNTIME_SANDBOX_VERSION，再运行更新。"
    return 1
  }
  image="$(workbench_get_env RUNTIME_SANDBOX_IMAGE)"
  current_version="$(workbench_get_env RUNTIME_SANDBOX_VERSION)"
  prompt_image_version new_version "Runtime Sandbox Docker tag" "$current_version"
  printf 'Runtime Sandbox: %s:%s -> %s:%s\n' "$image" "$current_version" "$image" "$new_version"
  confirm "更新将重建 Runtime，可能中断执行中的任务；确认继续？" y || return

  if ! workbench_compose config --quiet || ! ops pull "$image:$new_version" --force; then
    warn "配置检查或镜像拉取失败；环境文件和 Runtime 未修改。"
    return 1
  fi
  safe_current_version="${current_version//[^A-Za-z0-9_.-]/_}"
  backup_file="${WORKBENCH_ENV_FILE}.bak.update-runtime-sandbox-${safe_current_version}-$(date -u +%Y%m%dT%H%M%SZ)"
  [[ ! -e "$backup_file" ]] || die "备份文件已存在：$backup_file"
  cp -a -- "$WORKBENCH_ENV_FILE" "$backup_file" || return 1
  workbench_set_env RUNTIME_SANDBOX_VERSION "$new_version" || return 1

  if workbench_compose config --quiet &&
    compose_recreate workbench_compose workbench-runtime-node; then
    container_id="$(workbench_compose ps -q workbench-runtime-node)" || return 1
    configured_image="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$container_id" |
      sed -n 's/^RUNTIME_SANDBOX_IMAGE=//p')" || return 1
    if [[ "$configured_image" == "$image:$new_version" ]]; then
      success "Runtime 已重建并加载 Sandbox 镜像 ${image}:${new_version}；已有 Sandbox 不会被此脚本重建。"
      return
    fi
  fi
  warn "Runtime 更新或配置验证失败。备份位于 ${backup_file}；请检查容器日志。未自动回退，避免掩盖已执行的启动迁移。"
  return 1
}

workbench_env_exists() {
  if [[ ! -f "$WORKBENCH_ENV_FILE" ]]; then
    warn "尚未生成 .env.workbench，请先部署 Workbench。"
    return 1
  fi
}

service_update_menu() {
  local choice=""

  while true; do
    printf '\n服务更新菜单：\n'
    printf '  1) Studio API\n'
    printf '  2) Studio Frontend\n'
    printf '  3) Studio Node Sandbox\n'
    printf '  4) Workbench API\n'
    printf '  5) Workbench Frontend\n'
    printf '  6) Workbench Runtime\n'
    printf '  7) Workbench Runtime Gateway\n'
    printf '  8) Runtime Sandbox 镜像\n'
    printf '  9) PostgreSQL\n'
    printf ' 10) Redis\n'
    printf ' 11) RabbitMQ\n'
    printf ' 12) MinIO\n'
    printf '  0) 返回\n'
    read -r -p '请选择 [0-12]: ' choice
    case "$choice" in
      1)
        enforce_studio_cookie_mode
        update_service_version "Studio API" studio_get_env studio_set_env studio_compose STUDIO_IMAGE STUDIO_VERSION studio 240 y "$STUDIO_ENV_FILE"
        ;;
      2)
        enforce_studio_cookie_mode
        update_service_version "Studio Frontend" studio_get_env studio_set_env studio_compose STUDIO_FRONTEND_IMAGE STUDIO_FRONTEND_VERSION studio-frontend 240 y "$STUDIO_ENV_FILE"
        ;;
      3)
        enforce_studio_cookie_mode
        update_service_version "Studio Node Sandbox" studio_get_env studio_set_env studio_compose NODE_SANDBOX_IMAGE NODE_SANDBOX_VERSION node-sandbox 240 y "$STUDIO_ENV_FILE"
        ;;
      4)
        if workbench_env_exists; then
          warn "Workbench API 启动时可能执行数据库迁移，镜像恢复不会自动撤销迁移。"
          update_service_version "Workbench API" workbench_get_env workbench_set_env workbench_compose WORKBENCH_IMAGE WORKBENCH_VERSION workbench 300 y "$WORKBENCH_ENV_FILE"
        fi
        ;;
      5) if workbench_env_exists; then update_service_version "Workbench Frontend" workbench_get_env workbench_set_env workbench_compose WORKBENCH_FRONTEND_IMAGE WORKBENCH_FRONTEND_VERSION workbench-frontend 300 y "$WORKBENCH_ENV_FILE"; fi ;;
      6) if workbench_env_exists; then update_service_version "Workbench Runtime" workbench_get_env workbench_set_env workbench_compose RUNTIME_IMAGE RUNTIME_VERSION workbench-runtime-node 300 y "$WORKBENCH_ENV_FILE"; fi ;;
      7) if workbench_env_exists; then update_service_version "Workbench Runtime Gateway" workbench_get_env workbench_set_env workbench_compose RUNTIME_NGINX_IMAGE RUNTIME_NGINX_VERSION workbench-runtime 300 y "$WORKBENCH_ENV_FILE"; fi ;;
      8) if workbench_env_exists; then update_runtime_sandbox_image; fi ;;
      9)
        warn "更新 PostgreSQL 前必须完成数据库备份并确认版本升级兼容性。"
        update_service_version PostgreSQL dotenv_get set_env middleware_compose POSTGRES_IMAGE POSTGRES_VERSION postgresql 240 n "$ENV_FILE"
        ;;
      10)
        warn "更新 Redis 前必须完成备份并确认版本升级兼容性。"
        update_service_version Redis dotenv_get set_env middleware_compose REDIS_IMAGE REDIS_VERSION redis 240 n "$ENV_FILE"
        ;;
      11)
        warn "更新 RabbitMQ 前必须完成备份并确认版本升级兼容性。"
        update_service_version RabbitMQ dotenv_get set_env middleware_compose RABBITMQ_IMAGE RABBITMQ_VERSION rabbitmq 240 n "$ENV_FILE"
        ;;
      12)
        warn "更新 MinIO 前必须完成对象存储备份并确认版本升级兼容性。"
        update_service_version MinIO dotenv_get set_env middleware_compose MINIO_IMAGE MINIO_VERSION minio 240 n "$ENV_FILE"
        ;;
      0) return ;;
      *) warn "请输入 0 到 12 之间的数字。" ;;
    esac
  done
}

stop_studio_services() {
  studio_compose stop
  success "Studio 服务已停止。"
}

stop_workbench_services() {
  if ! workbench_env_exists; then
    return
  fi
  workbench_compose stop
  success "Workbench 服务已停止。"
}

stop_application_services() {
  stop_workbench_services
  stop_studio_services
}

stop_all_services() {
  stop_application_services
  middleware_compose stop
  success "共享中间件已停止。"
}

service_stop_menu() {
  local choice=""

  while true; do
    printf '\n服务停止菜单：\n'
    printf '  1) 停止 Studio\n'
    printf '  2) 停止 Workbench\n'
    printf '  3) 停止 Studio + Workbench\n'
    printf '  4) 停止全部（含共享中间件）\n'
    printf '  0) 返回\n'
    read -r -p '请选择 [0-4]: ' choice
    case "$choice" in
      1) if confirm "确认停止 Studio？" n; then stop_studio_services; fi ;;
      2) if confirm "确认停止 Workbench？" n; then stop_workbench_services; fi ;;
      3) if confirm "确认停止 Studio 和 Workbench？" n; then stop_application_services; fi ;;
      4) if confirm "确认停止全部服务（含共享中间件）？" n; then stop_all_services; fi ;;
      0) return ;;
      *) warn "请输入 0 到 4 之间的数字。" ;;
    esac
  done
}

container_state_is_abnormal() {
  local state="$1"
  local health="$2"
  local exit_code="$3"

  [[ "$health" == unhealthy ]] && return 0
  [[ "$state" == running ]] && return 1
  [[ "$state" == exited && "$exit_code" == 0 ]] && return 1
  return 0
}

show_container_health() {
  local ids_file=""
  local id=""
  local details=""
  local project=""
  local service=""
  local image=""
  local state=""
  local health=""
  local exit_code=""
  local restarts=""
  local count=0
  local issues=0

  ids_file="$(mktemp)"
  middleware_compose ps -a -q >> "$ids_file" 2>/dev/null || true
  studio_compose ps -a -q >> "$ids_file" 2>/dev/null || true
  if [[ -f "$WORKBENCH_ENV_FILE" ]]; then
    workbench_compose ps -a -q >> "$ids_file" 2>/dev/null || true
  fi

  printf '\n%-20s %-28s %-12s %-10s %-8s %s\n' \
    "项目" "服务" "状态" "健康度" "重启次数" "镜像"
  while read -r id; do
    [[ -n "$id" ]] || continue
    details="$(docker inspect --format \
      '{{index .Config.Labels "com.docker.compose.project"}}{{"\t"}}{{index .Config.Labels "com.docker.compose.service"}}{{"\t"}}{{.Config.Image}}{{"\t"}}{{.State.Status}}{{"\t"}}{{if .State.Health}}{{.State.Health.Status}}{{else}}未配置{{end}}{{"\t"}}{{.State.ExitCode}}{{"\t"}}{{.RestartCount}}' \
      "$id" 2>/dev/null || true)"
    [[ -n "$details" ]] || continue
    IFS=$'\t' read -r project service image state health exit_code restarts <<< "$details"
    printf '%-20s %-28s %-12s %-10s %-8s %s\n' \
      "$project" "$service" "$state" "$health" "$restarts" "$image"
    count=$((count + 1))
    if container_state_is_abnormal "$state" "$health" "$exit_code"; then
      issues=$((issues + 1))
    fi
  done < <(sort -u "$ids_file")
  unlink "$ids_file"

  if ((count == 0)); then
    warn "未找到 BasilOS Compose 容器。"
  elif ((issues == 0)); then
    success "共检查 $count 个容器，未发现异常状态。"
  else
    warn "共检查 $count 个容器，其中 $issues 个状态异常；请查看对应容器日志。"
  fi
}

# Operations shared by first installation and subsequent maintenance.
compose_recreate() { ops up "${1%_compose}" "$2" --recreate --no-deps; }

ops() { python3 "$DEPLOY_DIR/deploy-support.py" "$@"; }

environment_check() {
  if ! command -v python3 >/dev/null || ! command -v curl >/dev/null ||
    ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
    confirm '缺少 Python 3、curl、Docker 或 Compose，是否安装缺少的组件？' y || return 1
    bash "$DEPLOY_DIR/install-docker.sh" || return 1
  fi
  docker info >/dev/null 2>&1 || { warn 'Docker 未启动或无访问权限；Linux 可用 sudo bash deploy.sh。'; return 1; }
  docker compose up --help | grep -q -- '--wait' || { warn 'Compose 版本过旧，请升级 Compose 插件。'; return 1; }
  require_command python3
  require_command curl
  ops check-files || return 1
  success "环境检查通过：$(uname -s)/$(uname -m)"
}

restore_middleware_modes() {
  local files
  files="$(dotenv_get COMPOSE_FILE)"
  POSTGRES_MODE=external; REDIS_MODE=external; RABBITMQ_MODE=external; STORAGE_MODE=external
  [[ "$files" != *compose/db.yaml* ]] || POSTGRES_MODE=local
  [[ "$files" != *compose/cache.yaml* ]] || REDIS_MODE=local
  [[ "$files" != *compose/mq.yaml* ]] || RABBITMQ_MODE=local
  [[ "$files" != *compose/storage.yaml* ]] || STORAGE_MODE=local
  COMPOSE_FILES="$files"
}

existing_middleware_test() {
  case "$1" in
    postgresql)
      if [[ "$POSTGRES_MODE" == local ]]; then
        test_postgresql_local "$(dotenv_get POSTGRESQL_USERNAME)" "$(dotenv_get POSTGRESQL_PASSWORD)" "$(dotenv_get POSTGRESQL_BOOTSTRAP_DATABASE)"
      else
        ops pull "$(dotenv_get POSTGRES_IMAGE):$(dotenv_get POSTGRES_VERSION)" || return 1
        test_postgresql_external "$(dotenv_get POSTGRESQL_HOST)" "$(dotenv_get POSTGRESQL_PORT)" "$(dotenv_get POSTGRESQL_USERNAME)" "$(dotenv_get POSTGRESQL_PASSWORD)" "$(dotenv_get POSTGRESQL_BOOTSTRAP_DATABASE)"
      fi ;;
    redis)
      if [[ "$REDIS_MODE" == local ]]; then
        test_redis_local "$(dotenv_get REDIS_PASSWORD)"
      else
        ops pull "$(dotenv_get REDIS_IMAGE):$(dotenv_get REDIS_VERSION)" || return 1
        test_redis_external "$(dotenv_get REDIS_HOST)" "$(dotenv_get REDIS_PORT)" "$(dotenv_get REDIS_PASSWORD)" "$(dotenv_get REDIS_SSL)"
      fi ;;
    rabbitmq)
      local host port
      host="$(dotenv_get RABBITMQ_HOST)"; port="$(dotenv_get RABBITMQ_MANAGEMENT_PORT)"
      if [[ "$RABBITMQ_MODE" == local ]]; then host=127.0.0.1; port="$(dotenv_get RABBITMQ_MANAGEMENT_HOST_PORT)"; fi
      test_rabbitmq_endpoint "$host" "$port" "$(dotenv_get RABBITMQ_USERNAME)" "$(dotenv_get RABBITMQ_PASSWORD)" ;;
    minio)
      if [[ "$STORAGE_MODE" == local ]]; then
        middleware_compose exec -T minio curl --fail --silent http://127.0.0.1:9000/minio/health/ready >/dev/null
      else
        curl --fail --silent --show-error --connect-timeout 10 --max-time 20 "$(dotenv_get MINIO_EXPOSE_URL)/minio/health/ready" >/dev/null
      fi ;;
    aliyun-oss) test_url_reachable "$(dotenv_get ALI_OSS_ENDPOINT)" ;;
    azure-blob) test_url_reachable "$(dotenv_get AZURE_BLOB_ENDPOINT)" ;;
  esac
}

reuse_middleware() {
  local service="$1" keys='' key value mode=external choice id
  case "$service" in
    postgresql) keys='POSTGRESQL_HOST POSTGRESQL_PORT POSTGRESQL_USERNAME POSTGRESQL_PASSWORD POSTGRESQL_BOOTSTRAP_DATABASE'; mode="$POSTGRES_MODE" ;;
    redis) keys='REDIS_HOST REDIS_PORT REDIS_PASSWORD'; mode="$REDIS_MODE" ;;
    rabbitmq) keys='RABBITMQ_HOST RABBITMQ_PORT RABBITMQ_USERNAME RABBITMQ_PASSWORD RABBITMQ_VIRTUAL_HOST'; mode="$RABBITMQ_MODE" ;;
    storage)
      service="$(dotenv_get FILE_SERVICE_SELECTOR)"; mode="$STORAGE_MODE"
      case "$service" in
        minio) keys='MINIO_HOST MINIO_PORT MINIO_USERNAME MINIO_PASSWORD MINIO_EXPOSE_URL' ;;
        aliyun-oss) keys='ALI_OSS_ACCESS_ID ALI_OSS_ACCESS_KEY ALI_OSS_ENDPOINT' ;;
        azure-blob) keys='AZURE_BLOB_ACCOUNT_NAME AZURE_BLOB_ACCOUNT_KEY AZURE_BLOB_ENDPOINT' ;;
        *) return 1 ;;
      esac ;;
  esac
  while read -r key; do
    value="$(dotenv_get "$key")"
    if [[ -z "$value" || "$value" == *CHANGE_ME* ]]; then
      if [[ "$mode" == local ]] && [[ -n "$(middleware_compose ps -a -q "$service" 2>/dev/null)" ]]; then
        die "$service 已有容器但配置不完整；请恢复原 .env.middleware，不能用新密码覆盖已有数据。"
      fi
      return 1
    fi
  done < <(printf '%s\n' "$keys" | tr ' ' '\n')
  while true; do
    info "检查已有 ${service}（复用环境文件中的连接信息）"
    if existing_middleware_test "$service"; then
      success "$service 检查通过，跳过配置和重新部署。"
      return 0
    fi
    printf '  1) 用原配置启动/恢复本地服务  2) 重新检查  3) 重新配置  0) 返回主菜单\n'
    read -r -p '请选择 [0-3]: ' choice
    case "$choice" in
      1)
        if [[ "$mode" == local ]]; then
          ops up middleware "$service" || die "$service 恢复失败；配置已保留。"
          if [[ "$service" == postgresql ]]; then middleware_compose run --rm postgresql-init || die '数据库初始化失败。'; fi
        else warn '此服务是外部中间件，请在服务所在主机恢复。'; fi ;;
      2) ;;
      3) confirm "确认重新配置 ${service}？已有数据的密码不会被自动重置。" n && return 1 ;;
      0) die '已保留配置，结束本次部署。' ;;
    esac
  done
}

restart_services() {
  local group="$1" service="${2-}" frontend id
  if [[ -n "$service" ]]; then
    id="$("${group}_compose" ps -a -q "$service")"
    [[ -n "$id" ]] || die '该服务尚未部署，请先用安装菜单。'
    ops up "$group" "$service" --recreate --no-deps
  else
    [[ -n "$("${group}_compose" ps -a -q)" ]] || die '该项目尚未部署，请先用安装菜单。'
    ops up "$group" --recreate
  fi
  # Refresh static backend DNS after recreation.
  for group in studio workbench; do
    frontend="${group}-frontend"
    if [[ -n "$("${group}_compose" ps -q "$frontend" 2>/dev/null)" ]]; then
      "${group}_compose" exec -T "$frontend" nginx -s reload
    fi
  done
  success '服务已重新创建，环境文件中的修改已生效。'
}

service_restart_menu() {
  local choice group service
  printf '\n重启并加载环境变量：\n  1) Studio 全部\n  2) Workbench 全部\n  3) Studio API\n  4) Studio Frontend\n  5) Node Sandbox\n  6) Workbench API\n  7) Workbench Frontend\n  8) Runtime Node\n  9) Runtime Gateway\n  10) PostgreSQL\n  11) Redis\n  12) RabbitMQ\n  13) MinIO\n  0) 返回\n'
  read -r -p '请选择 [0-13]: ' choice
  case "$choice" in
    0) return ;; 1) restart_services studio ;; 2) restart_services workbench ;;
    3) restart_services studio studio ;; 4) restart_services studio studio-frontend ;;
    5) restart_services studio node-sandbox ;; 6) restart_services workbench workbench ;;
    7) restart_services workbench workbench-frontend ;; 8) restart_services workbench workbench-runtime-node ;;
    9) restart_services workbench workbench-runtime ;; 10) restart_services middleware postgresql ;;
    11) restart_services middleware redis ;; 12) restart_services middleware rabbitmq ;; 13) restart_services middleware minio ;;
    *) warn '选项无效。' ;;
  esac
}

run_menu_action() {
  local status
  set +e
  ( set -Eeuo pipefail; "$@" )
  status=$?
  set -e
  [[ "$status" -eq 0 ]] || warn "操作未完成（退出码 ${status}），已返回菜单；请根据上方原因处理后重试。"
}

install_selected() {
  prepare_deployment
  "$1"
}

maintenance_selected() {
  prepare
  "$@"
}

diagnose_environment() {
  prepare
  local group
  for group in middleware studio workbench; do
    ops check-images "$group"
  done
  ops pull "$(workbench_get_env RUNTIME_SANDBOX_IMAGE):$(workbench_get_env RUNTIME_SANDBOX_VERSION)"
}

deployment_menu() {
  local choice=""

  while true; do
    printf '\nBasilOS 部署与运维菜单：\n'
    printf '  1) 配置并部署 Studio + Workbench\n'
    printf '  2) 配置并部署 Studio\n'
    printf '  3) 配置并部署 Workbench\n'
    printf '  4) 更新已部署服务的 Docker tag\n'
    printf '  5) 查看容器健康度\n'
    printf '  6) 停止服务\n'
    printf '  7) 重启服务（加载最新环境变量）\n'
    printf '  8) 配置域名与 HTTPS\n'
    printf '  9) 环境、部署文件与镜像检查\n'
    printf '  0) 退出\n'
    read -r -p '请选择 [0-9]: ' choice
    case "$choice" in
      1) run_menu_action install_selected deploy_all ;;
      2) run_menu_action install_selected deploy_studio ;;
      3) run_menu_action install_selected deploy_workbench ;;
      4) run_menu_action maintenance_selected service_update_menu ;;
      5) prepare_health_check; show_container_health ;;
      6) prepare_health_check; service_stop_menu ;;
      7) run_menu_action maintenance_selected service_restart_menu ;;
      8) run_menu_action maintenance_selected bash "$DEPLOY_DIR/setup-domain-ssl.sh" ;;
      9) run_menu_action diagnose_environment ;;
      0) return ;;
      *) warn "请输入 0 到 9 之间的数字。" ;;
    esac
  done
}

prepare() {
  [[ -t 0 ]] || die "该脚本需要在交互式终端中运行。"
  environment_check || die "环境检查未通过。"
  require_command docker
  require_command curl
  docker compose version >/dev/null
  docker info >/dev/null 2>&1 || die "Docker 服务不可用或当前用户无权访问。"
  [[ -f "$MIDDLEWARE_COMPOSE_FILE" ]] || die "缺少 docker-compose.middleware.yaml"
  [[ -f "$STUDIO_COMPOSE_FILE" ]] || die "缺少 docker-compose.studio.yaml"
  [[ -f "$ENV_TEMPLATE" ]] || die "缺少 .env.middleware.example"
  [[ -f "$STUDIO_ENV_TEMPLATE" ]] || die "缺少 .env.studio.example"

  cd "$DEPLOY_DIR"
  [[ ! -L "$ENV_FILE" ]] || die "拒绝修改符号链接环境文件：$ENV_FILE"
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    info "已创建 $ENV_FILE"
  fi
  chmod 600 "$ENV_FILE"

  [[ ! -L "$STUDIO_ENV_FILE" ]] || die "拒绝修改符号链接环境文件：$STUDIO_ENV_FILE"
  if [[ ! -f "$STUDIO_ENV_FILE" ]]; then
    cp "$STUDIO_ENV_TEMPLATE" "$STUDIO_ENV_FILE"
    info "已创建 $STUDIO_ENV_FILE"
  fi
  chmod 600 "$STUDIO_ENV_FILE"

  restore_middleware_modes
  prepare_workbench_env
  ensure_shared_network
}

prepare_health_check() {
  require_command docker
  docker compose version >/dev/null
  docker info >/dev/null 2>&1 || die "Docker 服务不可用或当前用户无权访问。"
  [[ -f "$MIDDLEWARE_COMPOSE_FILE" ]] || die "缺少 docker-compose.middleware.yaml"
  [[ -f "$STUDIO_COMPOSE_FILE" ]] || die "缺少 docker-compose.studio.yaml"
  [[ -f "$ENV_FILE" ]] || die "缺少 .env.middleware，请先完成部署。"
  [[ -f "$STUDIO_ENV_FILE" ]] || die "缺少 .env.studio，请先完成部署。"
  cd "$DEPLOY_DIR"
}

self_test() {
  local original_env_file="$ENV_FILE"
  local original_studio_env_file="$STUDIO_ENV_FILE"
  local original_workbench_env_file="$WORKBENCH_ENV_FILE"
  local test_file=""
  local studio_test_file=""
  local workbench_test_file=""
  local prompted_version=""
  local expected="pass#\$word\\tail"

  test_file="$(mktemp)"
  printf 'COMPOSE_FILE=docker-compose.middleware.yaml\nTEST_VALUE=old\n' > "$test_file"
  ENV_FILE="$test_file"
  set_env TEST_VALUE "$expected"
  [[ "$(dotenv_get TEST_VALUE)" == "$expected" ]]

  studio_test_file="$(mktemp)"
  printf 'ENABLE_HTTPS_COOKIES=true\n' > "$studio_test_file"
  STUDIO_ENV_FILE="$studio_test_file"
  enforce_studio_cookie_mode
  [[ "$(studio_get_env ENABLE_HTTPS_COOKIES)" == false ]]

  POSTGRES_MODE=local
  REDIS_MODE=external
  RABBITMQ_MODE=local
  STORAGE_MODE=external
  rebuild_compose_files
  [[ "$(dotenv_get COMPOSE_FILE)" == \
    'docker-compose.middleware.yaml,compose/db.yaml,compose/mq.yaml' ]]

  workbench_test_file="$(mktemp)"
  printf 'TEST_VALUE=old\nTEST_VERSION=CHANGE_ME_VERSION\nAPP_URL=http://deploy.example.com:31001\n' > "$workbench_test_file"
  WORKBENCH_ENV_FILE="$workbench_test_file"
  workbench_set_env TEST_VALUE "$expected"
  [[ "$(workbench_get_env TEST_VALUE)" == "$expected" ]]

  (
    prompt_url() { die "已有平台网关不应重复询问"; }
    workbench_set_env BASILOS_GATEWAY_HOST https://studio.example.com
    ensure_workbench_gateway
    [[ "$(workbench_get_env BASILOS_GATEWAY_HOST)" == https://studio.example.com/ ]]
    workbench_set_env BASILOS_GATEWAY_HOST CHANGE_ME_GATEWAY_URL
    prompt_url() { printf -v "$1" '%s' http://studio-frontend; }
    ensure_workbench_gateway
    [[ "$(workbench_get_env BASILOS_GATEWAY_HOST)" == http://studio-frontend/ ]]
  )

  parse_url 'https://files.example.com:9443/path'
  [[ "$URL_SCHEME" == https ]]
  [[ "$URL_AUTHORITY" == 'files.example.com:9443' ]]
  [[ "$URL_HOST" == files.example.com ]]
  [[ "$URL_PORT" == 9443 ]]

  image_version_valid 'v1.2.3-alpine'
  ! image_version_valid 'repo/image:tag'
  prompt_image_version prompted_version 'Test Docker tag' current <<< ''
  [[ "$prompted_version" == current ]]
  DEPLOYMENT_ACCESS_HOST=deploy.example.com
  [[ "$(deployment_access_url 38080)" == 'http://deploy.example.com:38080' ]]
  DEPLOYMENT_ACCESS_HOST='[2001:db8::1]'
  [[ "$(deployment_access_url 80)" == 'http://[2001:db8::1]:80' ]]
  DEPLOYMENT_ACCESS_HOST=
  ! container_state_is_abnormal running healthy 0
  ! container_state_is_abnormal exited 未配置 0
  container_state_is_abnormal exited 未配置 1

  (
    ensure_image_version workbench_get_env workbench_set_env TEST_VERSION Test <<< 'v1.2.3'
    [[ "$(workbench_get_env TEST_VERSION)" == v1.2.3 ]]

    DEPLOYMENT_ACCESS_HOST=deploy.example.com
    prompt_url() {
      [[ "$3" == 'http://deploy.example.com:38080' ]]
      printf -v "$1" '%s' "$3"
    }
    ensure_workbench_url APP_URL 'Test API' 38080 >/dev/null 2>&1
    # HTTP 同源代理可以与内部 API 映射使用不同端口，不能覆盖已有公网地址。
    [[ "$WORKBENCH_VALUE" == 'http://deploy.example.com:31001' ]]
    workbench_set_env APP_URL CHANGE_ME_WORKBENCH_API_URL
    ensure_workbench_url APP_URL 'Test API' 38080 >/dev/null 2>&1
    [[ "$WORKBENCH_VALUE" == 'http://deploy.example.com:38080' ]]
  )

  (
    local calls=""
    local up_arguments=""
    local updated_key=""
    local updated_value=""
    unset TEST_VERSION
    ops() { test_compose pull; }
    compose_recreate() { test_compose up --no-deps --pull never --force-recreate; }
    test_getter() {
      if [[ "$1" == TEST_IMAGE ]]; then printf 'repo/service'; else printf 'old'; fi
    }
    test_setter() {
      updated_key="$1"
      updated_value="$2"
    }
    test_compose() {
      calls+="$1 "
      case "$1" in
        ps) printf 'container-id\n' ;;
        config) return 0 ;;
        pull) [[ "${TEST_VERSION-}" == new ]] ;;
        up) up_arguments="$*" ;;
      esac
    }
    prompt_image_version() {
      printf -v "$1" '%s' new
    }
    confirm() {
      return 0
    }

    update_service_version Test test_getter test_setter test_compose \
      TEST_IMAGE TEST_VERSION service 10 y "$workbench_test_file" >/dev/null
    [[ "$updated_key" == TEST_VERSION ]]
    [[ "$updated_value" == new ]]
    # 初始 ps 运行在命令替换的子 Shell 中，不会修改父 Shell 的 calls。
    [[ "$calls" == 'config pull config up ps ' ]]
    [[ "$up_arguments" == *'--no-deps'* ]]
    [[ "$up_arguments" == *'--pull'* ]]
    [[ "$up_arguments" == *'never'* ]]
    [[ "$up_arguments" == *'--force-recreate'* ]]
    [[ "${TEST_VERSION+x}" != x ]]
    rm -f -- "${workbench_test_file}.bak.update-service-old-"*
  )

  (
    local setter_called=false
    unset TEST_VERSION
    ops() { test_compose pull; }
    compose_recreate() { test_compose up --no-deps --pull never --force-recreate; }
    test_getter() {
      if [[ "$1" == TEST_IMAGE ]]; then printf 'repo/service'; else printf 'old'; fi
    }
    test_setter() {
      setter_called=true
    }
    test_compose() {
      case "$1" in
        ps) printf 'container-id\n' ;;
        config) return 0 ;;
        pull) return 1 ;;
      esac
    }
    prompt_image_version() {
      printf -v "$1" '%s' new
    }
    confirm() {
      return 0
    }

    ! update_service_version Test test_getter test_setter test_compose \
      TEST_IMAGE TEST_VERSION service 10 y "$workbench_test_file" >/dev/null 2>&1
    [[ "$setter_called" == false ]]
    [[ "${TEST_VERSION+x}" != x ]]
  )

  (
    local calls=""
    prepare() {
      calls+="prepare "
    }
    run_menu_action() { "$@"; }
    service_update_menu() {
      calls+="update"
    }

    main <<< '0' >/dev/null
    [[ -z "$calls" ]]
    deployment_menu <<< $'4\n0\n' >/dev/null
    [[ "$calls" == 'prepare update' ]]
  )

  (
    local calls=""
    workbench_env_exists() { return 0; }
    workbench_compose() { calls+="workbench "; }
    studio_compose() { calls+="studio "; }
    middleware_compose() { calls+="middleware"; }
    confirm() { return 0; }

    service_stop_menu <<< $'4\n0\n' >/dev/null
    [[ "$calls" == 'workbench studio middleware' ]]
  )

  unlink "$test_file"
  unlink "$studio_test_file"
  unlink "$workbench_test_file"
  ENV_FILE="$original_env_file"
  STUDIO_ENV_FILE="$original_studio_env_file"
  WORKBENCH_ENV_FILE="$original_workbench_env_file"
  success "deploy.sh 自检通过。"
}

main() {
  case "${1-}" in
    --self-test)
      self_test
      return
      ;;
    --update)
      [[ $# -eq 1 ]] || die "用法：./deploy.sh [--self-test|--update|--health|--check]"
      prepare
      service_update_menu
      return
      ;;
    --check)
      environment_check
      return
      ;;
    --health)
      [[ $# -eq 1 ]] || die "用法：./deploy.sh [--self-test|--update|--health|--check]"
      prepare_health_check
      show_container_health
      return
      ;;
    '') ;;
    *) die "用法：./deploy.sh [--self-test|--update|--health|--check]" ;;
  esac

  deployment_menu
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
