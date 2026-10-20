# Installa e avvia orbit-api dentro DevStack.

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

    write_uwsgi_config "$ORBIT_UWSGI_CONF" "$ORBIT_UWSGI" "/orbit" "" "orbit-api"
    # Un solo processo: il compito di creazione vive nella memoria del
    # processo che ha ricevuto la richiesta (docs/architettura.md). I thread
    # servono a non accodare le richieste mentre una aspetta Blazar o Heat.
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
    service=$(get_or_create_service orbit $ORBIT_SERVICE_TYPE "Orb effimeri")
    get_or_create_endpoint $service "$REGION_NAME" \
        "$SERVICE_PROTOCOL://$SERVICE_HOST/orbit"
}

# Nessun lease e creabile finche Blazar non conosce l'host di calcolo.
# La registrazione e ripetibile: un host gia registrato non si registra due volte.
function register_compute_hosts_in_blazar {
    local hosts host
    hosts=$(openstack --os-cloud devstack-admin hypervisor list \
        -f value -c "Hypervisor Hostname")
    for host in $hosts; do
        if openstack --os-cloud devstack-admin reservation host list \
                -f value -c hypervisor_hostname | grep -qx "$host"; then
            continue
        fi
        # Blazar e appena stato avviato dal suo plugin: la API puo non
        # rispondere ancora.
        for _ in $(seq 1 12); do
            openstack --os-cloud devstack-admin reservation host create "$host" && break
            sleep 5
        done
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
