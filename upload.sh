
#!/bin/bash

# Author 5stars217 https://5stars217.github.io/

# Global Variables
MANIFEST="./manifest.json"

DOCKER_HOST=$1
REPOSITORY=$2
LAYERPATH=$3
CONFIGPATH=$4

SIZE=
DIGEST=

LOCATION=

CONFIGSIZE=
CONFIGDIGEST=
LAYERSIZE=
LAYERDIGEST=

# Functions

function initiateUpload(){
   LOCATION=$(curl -X POST -siL -v  -H "Connection: close" $DOCKER_HOST/v2/$REPOSITORY/blobs/uploads | grep Location | sed '2q;d' | cut -d: -f2- | tr -d ' ' | tr -d '\r')
}

function patchLayer(){
    layersize=$(stat -c%s "$1")
    LOCATION=$(curl -X PATCH -v -H "Content-Type: application/octet-stream" \
        -H "Content-Length: $layersize" -H "Connection: close" --data-binary @"$1" \
        $LOCATION 2>&1 | grep 'Location' | cut -d: -f2- | tr -d ' ' | tr -d '\r')
    SIZE=$layersize
}

function putLayer(){
    DIGEST=sha256:$(sha256sum $1 | cut -d ' ' -f1)
    url="$LOCATION&digest=$DIGEST"
    curl -X PUT -v -H "Content-Length: 0" -H "Connection: close" $url

}

function uploadManifest(){
    ((size=$(stat -c%s "$MANIFEST")-1))
    curl -X PUT -vvv -H "Content-Type: application/vnd.docker.distribution.manifest.v2+json"\
    -H "Content-Length: $size" -H "Connection: close" \
    -d "$(cat "$MANIFEST")" $DOCKER_HOST/v2/$REPOSITORY/manifests/3.15.4
}

# Check Parameters

if [ $# -lt 4 ] 
    then
        echo "Error: No arguments supplied."
        echo "Usage: upload.sh <DOCKER_HOST> <REPOSITORY> <LAYER> <CONFIG>"
       exit 1
fi

#upload Layer
initiateUpload 
patchLayer $LAYERPATH
LAYERSIZE=$SIZE
putLayer $LAYERPATH
LAYERDIGEST=$DIGEST

#upload Config

initiateUpload
patchLayer $CONFIGPATH
CONFIGSIZE=$SIZE
putLayer $CONFIGPATH
CONFIGDIGEST=$DIGEST


cat > $MANIFEST << EOF
{
   "schemaVersion": 2,
   "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
   "config": {
       "mediaType": "application/vnd.docker.container.image.v1+json",
       "size": $CONFIGSIZE,
       "digest": "$CONFIGDIGEST"
   },
   "layers": [
        {
            "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
            "size":$LAYERSIZE,
            "digest": "$LAYERDIGEST"
        }
    ]
 }
EOF

uploadManifest
