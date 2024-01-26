# Makefile
merge-bindings:
	mkdir -p ananke/bindings/
	if [ ! -d /tmp/yang ]; then\
		git clone https://github.com/YangModels/yang.git /tmp/yang;\
		sed -i 's/type xr2:Hex-integer/type string/g' /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-access-list-datatypes.yang;\
	fi

	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/xr_route_policy \
	  --use-xpathhelper \
	  -p /tmp/yang/standard/ietf/RFC \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-types.yang \
	  /tmp/yang/vendor/cisco/xr/7921/cisco-semver.yang \
	  -f pybind \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-policy-repository-cfg.yang

	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/xr_object_groups \
	  --use-xpathhelper \
	  -p /tmp/yang/standard/ietf/RFC \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-types.yang \
	  /tmp/yang/vendor/cisco/xr/7921/cisco-semver.yang \
	  -f pybind \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-infra-objmgr-cfg.yang

bindings:
	mkdir -p ananke/bindings/
	if [ ! -d /tmp/yang ]; then\
		git clone https://github.com/YangModels/yang.git /tmp/yang;\
		sed -i 's/type xr2:Hex-integer/type string/g' /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-access-list-datatypes.yang;\
	fi
	if [ ! -d /tmp/openconfig ]; then\
		git clone https://github.com/openconfig/public.git /tmp/openconfig;\
		git -C /tmp/openconfig checkout tags/v2.0.0;\
	fi
	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/nxos_bgp \
      --use-xpathhelper \
      -p /tmp/yang/standard/ietf/RFC -p /tmp/yang/vendor/cisco/nx/9.3-11/Cisco-NX-OS-device.yang \
      -f pybind --lax-quote-checks \
	  ./ananke/yang/Cisco-NX-OS-device.yang

	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/oc_routing_policy \
      --use-xpathhelper \
      -p /tmp/yang/standard/ietf/RFC \
	  -p /tmp/openconfig/release/models/interfaces/ \
	  -p /tmp/openconfig/release/models/types/ \
	  /tmp/openconfig/release/models/bgp/openconfig-bgp-policy.yang \
	  /tmp/openconfig/release/models/bgp/openconfig-bgp-types.yang \
	  /tmp/openconfig/release/models/bgp/openconfig-bgp-errors.yang \
	  /tmp/openconfig/release/models/policy/openconfig-policy-types.yang \
	  /tmp/openconfig/release/models/openconfig-extensions.yang \
	  /tmp/openconfig/release/models/optical-transport/openconfig-transport-types.yang \
	  /tmp/openconfig/release/models/platform/openconfig-platform-types.yang \
      -f pybind --lax-quote-checks \
	  /tmp/openconfig/release/models/policy/openconfig-routing-policy.yang

	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/oc_network_instance \
      --use-xpathhelper \
      -p /tmp/yang/standard/ietf/RFC -p /tmp/openconfig/release/models/ \
      -f pybind \
	  /tmp/openconfig/release/models/network-instance/openconfig-network-instance.yang

	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/oc_interfaces \
      --use-xpathhelper \
      -p /tmp/yang/standard/ietf/RFC -p /tmp/openconfig/release/models/vlan \
	  -p /tmp/openconfig/release/models/types/ \
	  -p /tmp/openconfig/release/models/interfaces/ \
	  /tmp/openconfig/release/models/openconfig-extensions.yang \
	  /tmp/openconfig/release/models/optical-transport/openconfig-transport-types.yang \
	  /tmp/openconfig/release/models/platform/openconfig-platform-types.yang \
	  /tmp/openconfig/release/models/interfaces/openconfig-if-ip.yang \
      -f pybind \
	  /tmp/openconfig/release/models/interfaces/openconfig-interfaces.yang

	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/xr_route_policy \
	  --use-xpathhelper \
	  -p /tmp/yang/standard/ietf/RFC \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-types.yang \
	  /tmp/yang/vendor/cisco/xr/7921/cisco-semver.yang \
	  -f pybind \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-policy-repository-cfg.yang

	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/xr_um_interfaces \
	  --use-xpathhelper \
	  -p /tmp/yang/standard/ietf/RFC \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-types.yang \
	  /tmp/yang/vendor/cisco/xr/7921/cisco-semver.yang \
	  /tmp/yang/vendor/cisco/xr/7921/tailf-common.yang \
	  /tmp/yang/vendor/cisco/xr/7921/tailf-meta-extensions.yang \
	  /tmp/yang/vendor/cisco/xr/7921/tailf-cli-extensions.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-if-vrf-cfg.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-if-ip-address-cfg.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-flow-cfg.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-if-bundle-cfg.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-if-l2transport-cfg.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-l2-ethernet-cfg.yang \
	  -f pybind \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-interface-cfg.yang  \
	  --presence

	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/xr_object_groups \
	  --use-xpathhelper \
	  -p /tmp/yang/standard/ietf/RFC \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-types.yang \
	  /tmp/yang/vendor/cisco/xr/7921/cisco-semver.yang \
	  -f pybind \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-infra-objmgr-cfg.yang


	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/xr_bgp \
	  --use-xpathhelper \
	  -p /tmp/yang/standard/ietf/RFC \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-types.yang \
	  /tmp/yang/vendor/cisco/xr/7921/cisco-semver.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-ipv4-bgp-datatypes.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-infra-rsi-cfg.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-snmp-agent-cfg.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-ifmgr-cfg.yang \
	  -f pybind \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-ipv4-bgp-cfg.yang

	pyang --plugindir ${PYBINDPLUGIN} --split-class-dir ananke/bindings/xr_um_flow \
	  --use-xpathhelper \
	  -p /tmp/yang/standard/ietf/RFC \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-types.yang \
	  /tmp/yang/vendor/cisco/xr/7921/cisco-semver.yang \
	  /tmp/yang/vendor/cisco/xr/7921/tailf-common.yang \
	  /tmp/yang/vendor/cisco/xr/7921/tailf-meta-extensions.yang \
	  /tmp/yang/vendor/cisco/xr/7921/tailf-cli-extensions.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-interface-cfg.yang \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-if-l2transport-cfg.yang \
	  -f pybind \
	  /tmp/yang/vendor/cisco/xr/7921/Cisco-IOS-XR-um-flow-cfg.yang
	  