# pi-monitor
Pi HDMI Monitor

# Hardware

SupTronics X1301 V1.1 (Purchased from Amazon)
Pi4 4GB

# Software Install

Ref: https://suptronics.com/Raspberrypi/Interface/x1301-v1.1_software.html

sudo nano /boot/firmware/config.txt

Add two lines at the end of the file that reads like this:
dtoverlay=tc358743,4lane=1
dtoverlay=tc358743-audio

sudo nano 1080P60EDID.txt
00ffffffffffff005262888800888888
1c150103800000780aEE91A3544C9926
0F505400000001010101010101010101
010101010101011d007251d01e206e28
5500c48e2100001e8c0ad08a20e02d10
103e9600138e2100001e000000fc0054
6f73686962612d4832430a20000000FD
003b3d0f2e0f1e0a202020202020014f
020322444f841303021211012021223c
3d3e101f2309070766030c00300080E3
007F8c0ad08a20e02d10103e9600c48e
210000188c0ad08a20e02d10103e9600
138e210000188c0aa01451f01600267c
4300138e210000980000000000000000
00000000000000000000000000000000
00000000000000000000000000000015

v4l2-ctl -d /dev/v4l-subdev0 --set-edid=file=/home/pi/1080P60EDID.txt

media-ctl -d /dev/media3 -r

media-ctl -d /dev/media3 -l ''\''csi2'\'':4 -> '\''rp1-cfe-csi2_ch0'\'':0 [1]'
media-ctl -d /dev/media3 -V ''\''csi2'\'':0 [fmt:RGB888_1X24/1920x1080 field:none colorspace:srgb]'
media-ctl -d /dev/media3 -V ''\''csi2'\'':4 [fmt:RGB888_1X24/1920x1080 field:none colorspace:srgb]'


Ref:
https://pimylifeup.com/raspberry-pi-webcam-server/

MOTION_VERSION=4.7.0

wget https://github.com/Motion-Project/motion/releases/download/release-$MOTION_VERSION/$(lsb_release -cs)_motion_$MOTION_VERSION-1_$(dpkg --print-architecture).deb -O motion.deb

# Had to do this as next step hit error
sudo apt install libmicrohttpd-dev

sudo dpkg -i motion.deb

sudo nano /etc/motion/motion.conf
daemon off
stream_localhost off



