# install a venv so to keep your system interpreter clean
python3 -m venv env
source env/bin/activate

pip install -r dev-requirements.txt
pip install --upgrade pip
cp pre-commit .git/hooks/pre-commit
cp post-commit .git/hooks/post-commit
