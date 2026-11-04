#!/bin/bash
# Upload the built image to Glance as a NEW private image (project demo). Never touches existing images.
#   upload.sh
set -euo pipefail
V=tinycloud
B=/var/tmp/dev-251-build
F=$B/out/alpine-3.24-arm64-$V-dev251.qcow2
NAME=alpine-3.24-arm64-$V-dev251
sudo -n -u stack bash -c "cd /opt/stack/devstack && source openrc demo demo >/dev/null 2>&1 && 
  if [ -n \"\$(openstack image list --name $NAME -f value -c ID)\" ]; then echo 'image $NAME already exists' >&2; exit 1; fi &&
  openstack image create $NAME --file $F --disk-format qcow2 --container-format bare --min-disk 2 --private \
   --property hw_architecture=aarch64 --property hw_firmware_type=uefi --property hw_machine_type=virt \
   --property hw_rng_model=virtio --property hw_scsi_model=virtio-scsi --property img_config_drive=mandatory \
   --property os_distro=alpine --property os_version=3.24 \
   --property dev251_variant=$V --property dev251_sha256=$(sha256sum $F | cut -d' ' -f1) \
   -f yaml -c id -c name -c status -c size -c checksum -c owner -c visibility"
