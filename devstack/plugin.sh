# Installs and starts orbit-api inside DevStack.

XTRACE=$(set +o | grep xtrace)
set +o xtrace

function install_orbit {
    setup_develop $ORBIT_DIR
}

function configure_orbit {
    sudo install -d -o $STACK_USER $ORBIT_CONF_DIR
    rm -f $ORBIT_CONF

    iniset $ORBIT_CONF DEFAULT debug $ENABLE_DEBUG_LOG_LEVEL
    setup_logging $ORBIT_CONF
    configure_keystone_authtoken_middleware $ORBIT_CONF orbit
    iniset $ORBIT_CONF database connection "$(database_connection_url orbit)"

    iniset $ORBIT_CONF orbs image "$ORBIT_IMAGE_NAME"
    iniset $ORBIT_CONF orbs public_network "$PUBLIC_NETWORK_NAME"

    write_uwsgi_config "$ORBIT_UWSGI_CONF" "$ORBIT_UWSGI" "/orbit" "" "orbit-api"
    # A single process: the creation task lives in the memory of the process
    # that received the request (docs/architecture.md). The threads keep
    # requests from queuing while one waits for Blazar or Heat.
    iniset $ORBIT_UWSGI_CONF uwsgi processes 1
    iniset $ORBIT_UWSGI_CONF uwsgi threads 4
}

# The Orbs panel: Horizon loads it from the enabled files in its local
# directory. This phase precedes init_horizon (collectstatic, compress) and
# start_horizon in stack.sh.
ORBIT_DASHBOARD_ENABLED="_1950_project_orbit_panel_group.py _1951_project_orbs_panel.py"

function configure_orbit_dashboard {
    local file
    for file in $ORBIT_DASHBOARD_ENABLED; do
        cp $ORBIT_DIR/orbit/dashboard/enabled/$file \
            $HORIZON_DIR/openstack_dashboard/local/enabled/
    done
}

# The lab's egress proxy (docs/adr/0009): Smokescreen, a CONNECT proxy that
# admits only the listed hostnames and refuses private addresses and this
# host's own. It listens only on the public network's gateway address, the
# one the orbs' routers reach. DevStack creates that subnet and assigns the
# address to the host after post-config, so the proxy is configured in extra.
ORBIT_SMOKESCREEN_VERSION=v0.1.0
ORBIT_SMOKESCREEN_CONF=$ORBIT_CONF_DIR/smokescreen.yaml
ORBIT_SMOKESCREEN_ACL=$ORBIT_CONF_DIR/smokescreen-acl.yaml

function install_orbit_egress_proxy {
    local arch sum
    case $(uname -m) in
        aarch64)
            arch=arm64
            sum=f15ddd0dc2b2cbc6d7318f441928939eb9bedfab2a1881508af3096a1e24b7c9
            ;;
        x86_64)
            arch=amd64
            sum=4e1e447449e3cc653dae956208588722b5c8fe8ce894f633adc756a851d1ec46
            ;;
        *)
            die $LINENO "no Smokescreen release for $(uname -m)"
            ;;
    esac
    local name=smokescreen_${ORBIT_SMOKESCREEN_VERSION}_linux_$arch
    local dir
    dir=$(mktemp -d)
    curl -fsSL -o $dir/$name.tar.gz \
        https://github.com/stripe/smokescreen/releases/download/$ORBIT_SMOKESCREEN_VERSION/$name.tar.gz
    echo "$sum  $dir/$name.tar.gz" | sha256sum -c - \
        || die $LINENO "Smokescreen archive does not match its checksum"
    tar -xzf $dir/$name.tar.gz -C $dir
    sudo install -m 0755 $dir/$name/smokescreen /usr/local/bin/smokescreen
    rm -rf $dir
}

function configure_orbit_egress_proxy {
    if [[ ! "$ORBIT_EGRESS_PROXY_PORT" =~ ^[0-9]+$ ]]; then
        die $LINENO "ORBIT_EGRESS_PROXY_PORT is not a port: $ORBIT_EGRESS_PROXY_PORT"
    fi
    local gateway
    gateway=$(openstack --os-cloud devstack-admin subnet show \
        "$PUBLIC_SUBNET_NAME" -f value -c gateway_ip)
    if [[ -z "$gateway" || "$gateway" == "None" ]]; then
        die $LINENO "the public subnet has no gateway for the egress proxy to listen on"
    fi
    cat > $ORBIT_SMOKESCREEN_CONF <<EOF
ip: "$gateway"
port: $ORBIT_EGRESS_PROXY_PORT
acl_file: "$ORBIT_SMOKESCREEN_ACL"
# Orbs present no client certificate: the ACL's default rule applies to them.
allow_missing_role: true
EOF
    local domain domains
    IFS=, read -ra domains <<< "$ORBIT_EGRESS_PROXY_DOMAINS"
    {
        echo "version: v1"
        echo "services: []"
        echo "default:"
        echo "  project: orbit"
        echo "  action: enforce"
        if [[ ${#domains[@]} -eq 0 ]]; then
            echo "  allowed_domains: []"
        else
            echo "  allowed_domains:"
            for domain in "${domains[@]}"; do
                echo "    - \"$domain\""
            done
        fi
    } > $ORBIT_SMOKESCREEN_ACL
    iniset $ORBIT_CONF orbs egress_proxy "$gateway:$ORBIT_EGRESS_PROXY_PORT"
}

function start_orbit_egress_proxy {
    run_process orbit-egress-proxy \
        "/usr/local/bin/smokescreen --config-file $ORBIT_SMOKESCREEN_CONF"
}

# The orb image (docs/adr/0010): built by tools/image and published as a
# release asset of this repository. Every orb boots it, in any project, so it
# is public. Repeatable: an active image with its name is not uploaded again;
# one left incomplete by an interrupted upload stops the plugin.
ORBIT_IMAGE_URL=https://github.com/taekwondodev/orbit/releases/download/image-alpine-3.24.3/orbit-alpine-3.24.3-aarch64.qcow2
ORBIT_IMAGE_SHA256=a1063f4b86a86a3fd0d045be6c80c266ac80e709dd53faf31102c200fa28e560

function upload_orbit_image {
    local status
    status=$(openstack --os-cloud devstack-admin image list \
        --name "$ORBIT_IMAGE_NAME" -f value -c Status)
    if [[ "$status" == active ]]; then
        return
    fi
    if [[ -n "$status" ]]; then
        die $LINENO "image $ORBIT_IMAGE_NAME is $status, not active: delete it and run stack.sh again"
    fi
    local dir
    dir=$(mktemp -d)
    curl -fsSL -o $dir/image.qcow2 $ORBIT_IMAGE_URL
    echo "$ORBIT_IMAGE_SHA256  $dir/image.qcow2" | sha256sum -c - \
        || die $LINENO "the orb image does not match its checksum"
    # Without hw_scsi_model, Nova attaches the config drive through a
    # controller the image has no driver for, and the orb boots without
    # its key.
    openstack --os-cloud devstack-admin image create "$ORBIT_IMAGE_NAME" \
        --file $dir/image.qcow2 --disk-format qcow2 --container-format bare \
        --min-disk 2 --public \
        --property hw_architecture=aarch64 --property hw_firmware_type=uefi \
        --property hw_machine_type=virt --property hw_rng_model=virtio \
        --property hw_scsi_model=virtio-scsi \
        --property img_config_drive=mandatory \
        --property os_distro=alpine --property os_version=3.24
    rm -rf $dir
}

function init_orbit {
    # orbit-api creates its table when it starts.
    recreate_database orbit
}

function create_orbit_accounts {
    create_service_user orbit

    local service
    service=$(get_or_create_service orbit $ORBIT_SERVICE_TYPE "Ephemeral sandboxes")
    get_or_create_endpoint $service "$REGION_NAME" \
        "$SERVICE_PROTOCOL://$SERVICE_HOST/orbit"
}

# No lease can be created until Blazar knows the compute host.
# Registration is repeatable: a host already registered is not registered twice.
function register_compute_hosts_in_blazar {
    local hosts="" host
    # nova-compute may register its hypervisor a few seconds later.
    for _ in $(seq 1 12); do
        # DevStack maps hosts into the cell only after the extra phase, and
        # the Nova API does not show unmapped hypervisors. Repeatable.
        $NOVA_BIN_DIR/nova-manage --config-file $NOVA_CONF cell_v2 discover_hosts
        hosts=$(openstack --os-cloud devstack-admin hypervisor list \
            -f value -c "Hypervisor Hostname")
        [[ -n "$hosts" ]] && break
        sleep 5
    done
    if [[ -z "$hosts" ]]; then
        die $LINENO "orbit requires a compute node: no hypervisor in Nova to offer to Blazar"
    fi
    for host in $hosts; do
        if openstack --os-cloud devstack-admin reservation host list \
                -f value -c hypervisor_hostname | grep -qx "$host"; then
            continue
        fi
        # Blazar has just been started by its plugin: the API may not
        # respond yet.
        for _ in $(seq 1 12); do
            openstack --os-cloud devstack-admin reservation host create "$host" && continue 2
            sleep 5
        done
        die $LINENO "Blazar did not accept host $host: no lease could be created"
    done
}

function start_orbit {
    run_process orbit-api "$(which uwsgi) --procname-prefix orbit --ini $ORBIT_UWSGI_CONF"
}

function stop_orbit {
    stop_process orbit-api
}

function cleanup_orbit {
    remove_uwsgi_config "$ORBIT_UWSGI_CONF" orbit-api
    sudo rm -rf $ORBIT_CONF_DIR
    sudo rm -f /usr/local/bin/smokescreen
    local file
    for file in $ORBIT_DASHBOARD_ENABLED; do
        rm -f $HORIZON_DIR/openstack_dashboard/local/enabled/$file
    done
}

if is_service_enabled orbit-api; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing orbit"
        install_orbit
        if is_service_enabled orbit-egress-proxy; then
            install_orbit_egress_proxy
        fi
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        echo_summary "Configuring orbit"
        configure_orbit
        init_orbit
        create_orbit_accounts
        if is_service_enabled horizon; then
            configure_orbit_dashboard
        fi
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        echo_summary "Starting orbit"
        register_compute_hosts_in_blazar
        upload_orbit_image
        # orbit-api reads egress_proxy when it starts.
        if is_service_enabled orbit-egress-proxy; then
            configure_orbit_egress_proxy
        fi
        start_orbit
        if is_service_enabled orbit-egress-proxy; then
            start_orbit_egress_proxy
        fi
    fi

    if [[ "$1" == "unstack" ]]; then
        stop_orbit
        if is_service_enabled orbit-egress-proxy; then
            stop_process orbit-egress-proxy
        fi
    fi

    if [[ "$1" == "clean" ]]; then
        cleanup_orbit
    fi
fi

$XTRACE
