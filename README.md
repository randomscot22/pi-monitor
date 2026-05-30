# pi-monitor
Pi HDMI Monitor

# Hardware

SupTronics X1301 V1.1 (Purchased from Amazon)
Pi5 2GB

# Software Install

Ref: 

https://suptronics.com/Raspberrypi/Interface/x1301-v1.1_software.html

https://wiki.geekworm.com/X1301

https://github.com/geekworm-com/RPi5_hdmi_in_card

sudo nano /boot/firmware/config.txt

Add two lines at the end of the file that reads like this:  
dtoverlay=tc358743-pi5,4lane=1  
dtoverlay=tc358743-audio  




