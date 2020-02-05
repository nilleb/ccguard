# courtesy of DigitalOcean
# https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-18-04

# the domain to which the nginx configuration will be bound
DOMAIN=mysample.comain

sudo apt update
sudo apt install nginx
sudo apt install python3-pip python3-dev build-essential libssl-dev libffi-dev python3-setuptools
sudo apt install python3-venv

curl https://github.com/nilleb/ccguard/tree/master/docs/server-setup/ccguard.service --output ccguard.service.template
curl https://github.com/nilleb/ccguard/tree/master/docs/server-setup/nginx-ccguard --output nginx-ccguard.template

. envsubst_surrogate.cfg
printf "%s\n" "$(apply_shell_expansion ccguard.service.template)" > ccguard.service
printf "%s\n" "$(apply_shell_expansion cnginx-ccguard.template)" > nginx-ccguard

# gunicorn setup
python3 -m venv env
source env/bin/activate
pip install ccguard gunicorn flask
# TODO: eval the variables in ccguard.service
mv ccguard.service /etc/systemd/system/ccguard.service
sudo systemctl start ccguard
sudo systemctl enable ccguard
sudo systemctl status ccguard

# nginx setup
# TODO: eval the variables in nginx-ccguard
mv nginx-ccguard /etc/nginx/sites-available/ccguard
sudo ln -s /etc/nginx/sites-available/ccguard /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
