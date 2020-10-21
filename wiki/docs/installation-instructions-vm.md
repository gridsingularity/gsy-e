## How to Install D3A using a Virtual Machine (useful especially on Windows)

##### Install VirtualBox and Vagrant
It is recommended to use Chocolatey as a package management tool for Windows.

- Open your terminal (cmd.exe) as administrator
- Install [chocolatey](https://chocolatey.org/docs/installation) by running the following command : 
```
@"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))" && SET "PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin"
```
* Install Virtualbox from a Windows console
```
choco install virtualbox
```
* Install Vagrant (this is a software wrapper around virtualbox and other supervisors, that allows easy creation, download, and installation of virtual machines.
```
choco install vagrant
vagrant plugin install vagrant-disksize
```


### Install D3A while sharing a folder between guest and host machine via vagrant
##### Install D3A in a sharing folder
- Create a new-folder that you want to share across guest & host machine.
- Add the [Vagrantfile](https://github.com/gridsingularity/d3a/blob/master/vagrant/Vagrantfile) from d3a repository into your newly created folder.
- Open a terminal and go your folder with : ``` cd <path-to-your-folder> ```
- If it is your first time do : 
```
vagrant up  
```
Otherwise do step first :

- delete old vagrant images via : ```vagrant destroy --force```

- Remove residues of old vagrant boxes via :```vagrant box remove ubuntu/<your-box-name> --all --force```

At last do (note if the D3A is already installed and updated you don't need to do the steps above): 

Reload your virtual machine
``` 
vagrant reload 
```
Access terminal of your virtual machine to run D3A
```
vagrant ssh
```

##### Share folder to windows host
To share files between your virtual machine and windows we suggest to run these 3 commands :

Share d3a :
```
cp -r /home/vagrant/d3a /vagrant/
```

Share d3a-api-client :
```
cp -r /home/vagrant/d3a-api-client /vagrant/
```
If you have results you want to export to windows :
```
cd /home/vagrant/d3a-simulation/
zip -r <your-zip-filename>.zip ./<folder-to-be-zipped>/
cp -r <your-zip-filename>.zip /vagrant/
```

##### Run D3A simulation
To run a d3a simulation you need to be working under the `d3a` environment
```
source /home/vagrant/envs/d3a/bin/activate
```
Run simulation with : 
```
cd /vagrant/d3a
d3a run
```

##### How to get d3a-api-client in Vagrant
To run a d3a api client script you need to be working under the `api-client` environment
```
source envs/api-client/bin/activate
```
To run your API script, run the following command (templates [here](https://github.com/gridsingularity/d3a/tree/master/src/d3a/setup/odyssey_momentum)) : 
```
python your_api_script.py
```
