###Step 1: Installation prerequisites:

####make sure the command line compiler tools are installed:
```
xcode-select --install
```

(Select `Install` in the window that opens)

###Step 2: Install homebrew

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

###Step 3: Install other required libraries:

```
brew install automake libtool pkg-config libffi gmp openssl readline xz
```

###Step 4: Install pyenv:

```
brew install pyenv
echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n eval "$(pyenv init -)"\nfi' >> ~/.bash_profile
```

###Step 5: Close and re-open the terminal

###Step 6: Install Python 3.6 and set as default:

```
pyenv install 3.8.6
pyenv global 3.8.6
```

###Step 7: Install virtualenvwrapper:

```
pip3 install virtualenvwrapper
echo -e 'export WORKON_HOME=~/Envs\nsource ~/.pyenv/versions/3.8.6/bin/virtualenvwrapper.sh' >> ~/.bash_profile
```

###Step 8: Setup paths for compiling Python libraries:

```
echo -e 'BREW_PREFIX="$(brew --prefix openssl)"\nexport CFLAGS="-I${BREW_PREFIX}/include"\nexport LDFLAGS="-L${BREW_PREFIX}/lib"' >> ~/.bash_profile
```

###Step 9: Close and re-open the terminal

###Step 10: Clone gsy-e repository (do this inside the directory where you want the project to be):

```
git clone "https://github.com/gridsingularity/gsy-e.git"
cd gsy-e
```

###Step 11: Create and initialise gsy-e virtualenv

```
brew install npm
npm install --global ganache-cli
mkvirtualenv gsy-e
pip3 install pendulum pip-tools
pip3 install -e .
```

You now should have a working gsy-e setup.

For help in the terminal ani to test your installation, run `gsy-e run -–help`.
