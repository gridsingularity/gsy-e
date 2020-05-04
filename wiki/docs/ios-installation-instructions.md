## How to Install D3A on macOS

### Preparations 

##### Make sure the command line compiler tools are installed:

```
xcode-select --install
```
(Select 'Install' in the window that opens)


##### Install Homebrew

```
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

##### Install some libraries we need later:

```
brew install automake libtool pkg-config libffi gmp openssl readline xz
```

##### Install pyenv:

```
brew install pyenv
echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n eval "$(pyenv init -)"\nfi' >> ~/.bash_profile
```

#####  Close and re-open the terminal

#####  Install Python 3.6 and set as default:

```
pyenv install 3.6.3
pyenv global 3.6.3
```

#####  Install virtualenvwrapper:
```
pip install virtualenvwrapper
echo -e 'export WORKON_HOME=~/Envs\nsource ~/.pyenv/versions/3.6.3/bin/virtualenvwrapper.sh' >> ~/.bash_profile
```


#####  Setup paths for compiling python libraries:

```
echo -e 'BREW_PREFIX="$(brew --prefix openssl)"\nexport CFLAGS="-I${BREW_PREFIX}/include"\nexport LDFLAGS="-L${BREW_PREFIX}/lib"' >> ~/.bash_profile
```


### Installation

##### Close and re-open the terminal

##### Clone d3a repository (do this inside the directory where you want the project to be):
```
git clone "https://github.com/gridsingularity/d3a.git"
cd d3a
```

##### Create and initialize d3a virtualenv
```
brew install npm 
npm install --global ganache-cli
mkvirtualenv d3a
pip install pendulum pip-tools
pip install -e . 
```

#####  Install 

#####  Done, you now should have a working d3a setup.


Now, if you run `d3a run -–help` , the help of d3a should be shown.
