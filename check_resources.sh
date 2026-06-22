#!/bin/bash
# check_resources.sh - FINAL VERSION
# Handles: unlimited memory, malformed output, WSL quirks

set -euo pipefail

REFRESH_RATE=${1:-1}

# Colors
GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; BLUE="\033[34m"; CYAN="\033[36m"; RESET="\033[0m"; BOLD="\033[1m"

clear
echo -e "${BOLD}${CYAN}ComfyUI + FastAPI Resource Monitor${RESET}"
echo -e "${YELLOW}Press Ctrl+C to stop${RESET}\n"

trap 'echo -e "\n${GREEN}Monitoring stopped.${RESET}"; exit 0' INT

while true; do
    NOW=$(date '+%H:%M:%S')

    # === 1. GPU ===
    GPU_LINE=$(nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits 2>/dev/null || echo "N/A,0,0,0,0")
    IFS=',' read -r GPU_NAME GPU_USED GPU_TOTAL GPU_UTIL GPU_TEMP <<< "$GPU_LINE"

    # === 2. Docker Stats (RAW) ===
    RAW_STATS=$(docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null || echo "")

    # === 3. Disk ===
    if [[ -d "shared_data" ]]; then
        DISK_USED=$(du -sh shared_data 2>/dev/null | cut -f1 || echo "N/A")
        DISK_TOTAL=$(df -h . | tail -1 | awk '{print $2}' 2>/dev/null || echo "N/A")
        DISK_PERC=$(df . | tail -1 | awk '{print $5}' | tr -d '%' 2>/dev/null || echo "0")
    else
        DISK_USED="N/A"; DISK_TOTAL="N/A"; DISK_PERC="0"
    fi

    # === Print ===
    clear
    echo -e "${BOLD}${CYAN}Resource Monitor - $NOW${RESET}"
    echo -e "----------------------------------------"

    # GPU
    if [[ "$GPU_NAME" != "N/A" ]] && [[ $GPU_TOTAL -gt 0 ]]; then
        GPU_MEM_STR="${GPU_USED}MiB / ${GPU_TOTAL}MiB"
        UTIL_COLOR=$([[ $GPU_UTIL -gt 80 ]] && echo "$RED" || echo "$GREEN")
        TEMP_COLOR=$([[ $GPU_TEMP -gt 75 ]] && echo "$RED" || echo "$YELLOW")
        echo -e "GPU: ${BOLD}${GPU_NAME}${RESET}"
        echo -e "  VRAM: $GPU_MEM_STR  |  Util: ${UTIL_COLOR}${GPU_UTIL}%${RESET}  |  Temp: ${TEMP_COLOR}${GPU_TEMP}°C${RESET}"
    else
        echo -e "GPU: ${YELLOW}Not detected${RESET}"
    fi

    # Containers
    echo -e "\nContainers:"
    echo -e "  NAME       CPU %    MEM USAGE / LIMIT     MEM %"
    echo -e "  ---------  -------  --------------------  -------"

    CONTAINER_FOUND=false

    while IFS=$'\t' read -r NAME CPU MEM_USAGE MEM_PERC; do
        [[ -z "$NAME" ]] && continue
        [[ "$NAME" != *"comfyui"* && "$NAME" != *"fastapi"* ]] && continue

        CONTAINER_FOUND=true

        # Clean MEM_USAGE: "14.11GiB / 32GiB" → USAGE=14.11GiB, LIMIT=32GiB
        USAGE="N/A"; LIMIT="N/A"
        if [[ "$MEM_USAGE" =~ ^([0-9.]+[GMK]iB)[[:space:]]/[[:space:]]([0-9.]+[GMK]iB)$ ]]; then
            USAGE="${BASH_REMATCH[1]}"
            LIMIT="${BASH_REMATCH[2]}"
        elif [[ "$MEM_USAGE" =~ ^([0-9.]+[GMK]iB)[[:space:]]/$ ]]; then
            USAGE="${BASH_REMATCH[1]}"
            LIMIT="unlimited"
        fi

        # MEM_PERC: use if valid, else calculate or show N/A
        if [[ "$MEM_PERC" =~ ^[0-9.]+%$ ]]; then
            PERC_VAL="${MEM_PERC%%%}"
        elif [[ "$LIMIT" != "unlimited" ]] && [[ "$USAGE" =~ ^([0-9.]+)([GMK])iB$ ]] && [[ "$LIMIT" =~ ^([0-9.]+)([GMK])iB$ ]]; then
            U_VAL=${BASH_REMATCH[1]}; U_UNIT=${BASH_REMATCH[2]}
            L_VAL=${BASH_REMATCH[1]}; L_UNIT=${BASH_REMATCH[2]}
            if [[ "$U_UNIT" == "$L_UNIT" ]]; then
                PERC_VAL=$(awk "BEGIN {printf \"%.1f\", $U_VAL * 100 / $L_VAL}")
            else
                PERC_VAL="N/A"
            fi
        else
            PERC_VAL="N/A"
        fi

        # Color
        if [[ "$PERC_VAL" =~ ^[0-9.]+$ ]] && (( $(echo "$PERC_VAL > 80" | bc -l 2>/dev/null || echo 0) )); then
            MEM_COLOR=$RED
        elif [[ "$PERC_VAL" =~ ^[0-9.]+$ ]] && (( $(echo "$PERC_VAL > 50" | bc -l 2>/dev/null || echo 0) )); then
            MEM_COLOR=$YELLOW
        else
            MEM_COLOR=$GREEN
        fi

        printf "  %-9s  ${BLUE}%6s${RESET}  %10s / %-8s  ${MEM_COLOR}%6s${RESET}\n" \
            "$NAME" "$CPU" "$USAGE" "$LIMIT" "${PERC_VAL}%"

    done <<< "$(echo "$RAW_STATS" | tr -s ' ')"

    if ! $CONTAINER_FOUND; then
        echo -e "  ${YELLOW}No containers running${RESET}"
    fi

    # Disk
    DISK_COLOR=$([[ $DISK_PERC -gt 80 ]] && echo "$RED" || echo "$GREEN")
    echo -e "\nDisk (shared_data): ${DISK_COLOR}${DISK_USED} / ${DISK_TOTAL} (${DISK_PERC}%)${RESET}"

    sleep "$REFRESH_RATE"
done