#!/bin/sh
# Auto-configure default IPv4 gateway and subnet route for wireless connections
if [ "${1%[0-9]*}" = "wlan" ] && { [ "$2" = "up" ] || [ "$2" = "dhcp4-change" ]; }; then
    if [ -n "$DHCP4_IP_ADDRESS" ] && [ -n "$DHCP4_ROUTERS" ]; then
        /usr/bin/python3 -c "
import ipaddress, subprocess
ip = '$DHCP4_IP_ADDRESS'
mask = '${DHCP4_SUBNET_MASK:-255.255.255.0}'
router = '$DHCP4_ROUTERS'
iface = '$1'
try:
    net = str(ipaddress.IPv4Interface(f'{ip}/{mask}').network)
    subprocess.call(['/sbin/ip', 'route', 'replace', net, 'dev', iface, 'proto', 'kernel', 'scope', 'link', 'src', ip])
    subprocess.call(['/sbin/ip', 'route', 'replace', 'default', 'via', router, 'dev', iface])
except Exception:
    pass
" >/dev/null 2>&1 &
    fi
fi
