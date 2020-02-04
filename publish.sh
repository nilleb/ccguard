python3 -m venv env
source env/bin/activate

pip install twine
python3 -m twine upload dist/*
