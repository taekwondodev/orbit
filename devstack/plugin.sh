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

    iniset $ORBIT_CONF orbs default_image "$DEFAULT_IMAGE_NAME"
    iniset $ORBIT_CONF orbs public_network "$PUBLIC_NETWORK_NAME"
    if [[ "$DEFAULT_IMAGE_NAME" == cirros* ]]; then
        iniset $ORBIT_CONF orbs ssh_users "$DEFAULT_IMAGE_NAME:cirros"
    fi

    write_uwsgi_config "$ORBIT_UWSGI_CONF" "$ORBIT_UWSGI" "/orbit" "" "orbit-api"
    # A single process: the creation task lives in the memory of the process
    # that received the request (docs/architecture.md). The threads keep
    # requests from queuing while one waits for Blazar or Heat.
    iniset $ORBIT_UWSGI_CONF uwsgi processes 1
    iniset $ORBIT_UWSGI_CONF uwsgi threads 4
}

function init_orbit {
    recreate_database orbit
    orbit-dbsync --config-file $ORBIT_CONF
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
}

if is_service_enabled orbit-api; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing orbit"
        install_orbit
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        echo_summary "Configuring orbit"
        configure_orbit
        init_orbit
        create_orbit_accounts
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        echo_summary "Starting orbit"
        register_compute_hosts_in_blazar
        start_orbit
    fi

    if [[ "$1" == "unstack" ]]; then
        stop_orbit
    fi

    if [[ "$1" == "clean" ]]; then
        cleanup_orbit
    fi
fi

$XTRACE
