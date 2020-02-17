# courtesy of DigitalOcean
# https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-18-04

# the domain to which the nginx configuration will be bound
DOMAIN=mysample.comain
TOKEN=secret
use_ssl="true"

sudo apt update
sudo apt -y install nginx python3-pip python3-dev build-essential libssl-dev libffi-dev python3-setuptools python3-venv

curl -L https://raw.githubusercontent.com/nilleb/ccguard/master/docs/server-setup/ccguard.service --output ccguard.service.template
curl -L https://raw.githubusercontent.com/nilleb/ccguard/master/docs/server-setup/nginx-ccguard --output nginx-ccguard.template

mkdir $HOME/letsencrypt

curl -L https://raw.githubusercontent.com/nilleb/ccguard/master/docs/server-setup/envsubst_surrogate.cfg --output envsubst_surrogate.cfg

. envsubst_surrogate.cfg
printf "%s\n" "$(apply_shell_expansion ccguard.service.template)" > ccguard.service
printf "%s\n" "$(apply_shell_expansion nginx-ccguard.template)" > nginx-ccguard

# gunicorn setup
python3 -m venv env --system-site-packages
source env/bin/activate
pip install ccguard gunicorn flask
# TODO: eval the variables in ccguard.service
sudo mv ccguard.service /etc/systemd/system/ccguard.service
sudo systemctl start ccguard
sudo systemctl enable ccguard
sudo systemctl status ccguard

# nginx setup
# TODO: eval the variables in nginx-ccguard
sudo mv nginx-ccguard /etc/nginx/sites-available/ccguard
sudo ln -s /etc/nginx/sites-available/ccguard /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx

if [ "$use_ssl" == "true" ]; then
    curl -L https://raw.githubusercontent.com/nilleb/ccguard/master/docs/server-setup/nginx-ssl --output nginx-ssl.template
    printf "%s\n" "$(apply_shell_expansion nginx-ssl.template)" > nginx-ssl

    sudo apt-get install software-properties-common
    yes "" | sudo add-apt-repository ppa:certbot/certbot
    sudo apt-get update
    sudo apt-get install certbot
    sudo certbot certonly --webroot -w $HOME/letsencrypt -d $DOMAIN
    # to renew the certificate
    # sudo certbot renew
fi
