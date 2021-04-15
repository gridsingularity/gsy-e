###Step 1: Installation prerequisites:

####make sure the command line compiler tools are installed:
```
xcode-select --install
```

(Select `Install` in the window that opens)

###Step 2: Install homebrew

```
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
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

###Step 6: Install python 3.6 and set as default:

```
pyenv install 3.8.6
pyenv global 3.8.6
```

###Step 7: Install virtualenvwrapper:

```
pip install virtualenvwrapper
echo -e 'export WORKON_HOME=~/Envs\nsource ~/.pyenv/versions/3.8.3/bin/virtualenvwrapper.sh' >> ~/.bash_profile
```

###Step 8: Setup paths for compiling python libraries:

```
echo -e 'BREW_PREFIX="$(brew --prefix openssl)"\nexport CFLAGS="-I${BREW_PREFIX}/include"\nexport LDFLAGS="-L${BREW_PREFIX}/lib"' >> ~/.bash_profile
```

###Step 9: Close and re-open the terminal

###Step 10: Clone Grid Singularity D3A repository (do this inside the directory where you want the project to be):

```
git clone "https://github.com/gridsingularity/d3a.git"
cd d3a
```

###Step 11: Create and initialize d3a virtualenv

```
brew install npm 
npm install --global ganache-cli
mkvirtualenv d3a
pip install pendulum pip-tools
pip install -e . 
```

You now should have a working d3a setup.

For help in the terminal ani to test your installation, run `d3a run -–help`.
