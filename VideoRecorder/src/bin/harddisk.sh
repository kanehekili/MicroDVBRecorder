#!/bin/bash

OUTPUT="harddisk.txt"
printf "%-20s %-35s %6s %6s %6s %5s\n" "SMB-Name" "Device" "Size" "Used" "Avail" "Use%" | tee "$OUTPUT"

declare -A share_paths
current_share=""

while IFS= read -r line; do
    line="${line#"${line%%[![:space:]]*}"}"  # trim leading whitespace
    if [[ "$line" =~ ^\[(.+)\]$ ]]; then
        current_share="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ^path[[:space:]]*=[[:space:]]*(.+)$ ]]; then
        [[ -n "$current_share" && "$current_share" != "global" ]] \
            && share_paths["$current_share"]="${BASH_REMATCH[1]}"
    fi
done < <(testparm -s 2>/dev/null)

for share in $(echo "${!share_paths[@]}" | tr ' ' '\n' | sort); do
    path="${share_paths[$share]}"
    read -r dev size used avail usepct _ < <(df -h "$path" 2>/dev/null | tail -1)
    [[ -n "$dev" ]] && printf "%-20s %-35s %6s %6s %6s %5s\n" \
        "$share" "$dev" "$size" "$used" "$avail" "$usepct" | tee -a "$OUTPUT"
done
