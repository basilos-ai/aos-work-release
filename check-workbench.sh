#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.workbench}"
UPDATED_COUNT=0

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

pass() {
  printf '[PASS] %s\n' "$*"
}

info() {
  printf '[INFO] %s\n' "$*"
}

read_env() {
  local key="$1"
  awk -F= -v key="${key}" '
    $1 == key {
      value = substr($0, index($0, "=") + 1)
      sub(/\r$/, "", value)
      print value
      exit
    }
  ' "${ENV_FILE}"
}

write_env() {
  local key="$1"
  local value="$2"
  local current_value temp_file

  current_value="$(read_env "${key}")"
  if [[ "${current_value}" == "${value}" ]]; then
    pass "${key}=${value}"
    return
  fi

  temp_file="$(mktemp "${ENV_FILE}.tmp.XXXXXX")"
  if ! awk -F= -v key="${key}" -v value="${value}" '
    BEGIN { written = 0 }
    $1 == key {
      if (!written) {
        print key "=" value
        written = 1
      }
      next
    }
    { print }
    END {
      if (!written) print key "=" value
    }
  ' "${ENV_FILE}" >"${temp_file}"; then
    rm -f "${temp_file}"
    fail "无法更新 ${ENV_FILE} 中的 ${key}"
  fi

  chmod 600 "${temp_file}"
  mv "${temp_file}" "${ENV_FILE}"
  UPDATED_COUNT=$((UPDATED_COUNT + 1))
  info "已修正 ${key}: ${current_value:-<未配置>} -> ${value}"
}

append_candidate() {
  local candidate="$1"
  local existing
  [[ -n "${candidate}" ]] || return
  for existing in "${SOCKET_CANDIDATES[@]:-}"; do
    [[ "${existing}" == "${candidate}" ]] && return
  done
  SOCKET_CANDIDATES+=("${candidate}")
}

socket_responds() {
  local socket_path="$1"
  [[ -S "${socket_path}" ]] || return 1
  docker --host "unix://${socket_path}" version --format '{{.Server.Version}}' >/dev/null 2>&1
}

resolve_docker_socket() {
  local configured_socket context_host candidate
  configured_socket="$(read_env RUNTIME_DOCKER_SOCKET_PATH)"
  append_candidate "${configured_socket}"

  if [[ "${DOCKER_HOST:-}" == unix://* ]]; then
    append_candidate "${DOCKER_HOST#unix://}"
  fi

  context_host="$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)"
  if [[ "${context_host}" == unix://* ]]; then
    append_candidate "${context_host#unix://}"
  fi

  append_candidate '/var/run/docker.sock'
  append_candidate "/run/user/$(id -u)/docker.sock"
  if [[ -n "${HOME:-}" ]]; then
    append_candidate "${HOME}/.docker/run/docker.sock"
  fi

  for candidate in "${SOCKET_CANDIDATES[@]}"; do
    if socket_responds "${candidate}"; then
      printf '%s' "${candidate}"
      return
    fi
  done

  return 1
}

read_socket_gid() {
  local socket_path="$1"
  local gid
  # Docker Desktop 将挂载到 Linux 容器内的 Engine Socket 表现为 root:root；
  # macOS 宿主机 Socket 文件自身的组 ID 不能直接用于容器 group_add。
  if [[ "$(uname -s)" == 'Darwin' ]]; then
    printf '0'
    return
  fi
  if gid="$(stat -c '%g' "${socket_path}" 2>/dev/null)"; then
    printf '%s' "${gid}"
    return
  fi
  if gid="$(stat -f '%g' "${socket_path}" 2>/dev/null)"; then
    printf '%s' "${gid}"
    return
  fi
  return 1
}

main() {
  local docker_socket docker_gid
  SOCKET_CANDIDATES=()

  [[ -e "${ENV_FILE}" ]] || fail "未找到 ${ENV_FILE}；请先从 .env.workbench.example 创建该文件"
  [[ -f "${ENV_FILE}" ]] || fail "${ENV_FILE} 不是普通文件"
  [[ ! -L "${ENV_FILE}" ]] || fail "拒绝修改符号链接环境文件：${ENV_FILE}"
  command -v docker >/dev/null 2>&1 || fail '缺少 docker 命令'
  command -v stat >/dev/null 2>&1 || fail '缺少 stat 命令'

  docker_socket="$(resolve_docker_socket)" || \
    fail '未找到当前用户可访问且 Docker Engine 能响应的 Unix Socket'
  docker_gid="$(read_socket_gid "${docker_socket}")" || \
    fail "无法读取 Docker Socket GID：${docker_socket}"
  [[ "${docker_gid}" =~ ^[0-9]+$ ]] || fail "Docker Socket GID 非法：${docker_gid}"

  # 当前发布镜像合同：Workbench 以 root 管理目录，Sandbox 以 1000:10001 运行。
  write_env USER_STORAGE_OWNER_UID 0
  write_env USER_STORAGE_GID 10001
  write_env SANDBOX_WORKSPACE_OWNER_UID 0
  write_env SANDBOX_WORKSPACE_UID 1000
  write_env SANDBOX_WORKSPACE_GID 10001
  write_env RUNTIME_DOCKER_SOCKET_PATH "${docker_socket}"
  write_env RUNTIME_DOCKER_GID "${docker_gid}"

  if ((UPDATED_COUNT > 0)); then
    pass "已更新 ${ENV_FILE}，共修正 ${UPDATED_COUNT} 项"
  else
    pass "${ENV_FILE} 中的 UID/GID 与 Docker Socket 配置均正确"
  fi
  info '脚本未检查或修改镜像、密钥、域名、容器状态、HTTP 服务和业务功能'
}

main "$@"
