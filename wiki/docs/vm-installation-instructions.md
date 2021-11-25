If the Grid Singularity Exchange is already installed and updated on your virtual machine you can skip to step 4.

###Step 1: Windows environment settings (not always required, please try starting with Step 2)

Enable Intel Virtualization on your computer in BIOS.

Go to your Windows Features setting and disable Windows Hypervisor Platform (or Hyper-V) and enable Virtual Machine Platform.

###Step 2: Install Virtualbox and Vagrant

It is recommended to use Chocolatey as a package management tool for Windows.

Open your terminal (cmd.exe) as administrator and install chocolatey by running the following command :

```
@"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))" && SET "PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin"
```

Install Virtualbox from a Windows console

```
choco install virtualbox
```

Install Vagrant (this is a software wrapper around virtualbox and other supervisors, that allows easy creation, download, and installation of virtual machines.

```
choco install vagrant
vagrant plugin install vagrant-disksize
```

###Step 3: Install Grid Singularity Exchange while sharing a folder between guest and host machine via vagrant

Create a new-folder that you want to share across guest and host machines.

Add the Vagrantfile from Grid Singularity Exchange repository into your newly created folder.

Open a terminal and go into your newly-created folder with:

```
cd <path-to-your-folder>
```

If it is your first time do:

```
vagrant up
```

If vagrant was already running, please delete re-initialize with the following steps first :

* Delete old vagrant images via :

```
vagrant destroy --force
```

* Remove residues of old vagrant boxes via :

```
vagrant box remove ubuntu/<your-box-name> --all --force
```

###Step 4: Reload your virtual machine:

```
vagrant reload
```

###Step 5: Access your virtual machine terminal to run Grid Singularity Exchange:

```
vagrant ssh
```

###Step 6: Share folder to Windows host by running these three commands:

```
cp -r /home/vagrant/gsy-e/vagrant/
```

Share gsy-e-sdk:

```
cp -r /home/vagrant/gsy-e-sdk/vagrant/
```

If you have results you want to export to Windows :

```
cd /home/vagrant/gsy-e-simulation/
zip -r <your-zip-filename>.zip ./<folder-to-be-zipped>/
cp -r <your-zip-filename>.zip /vagrant/
```

###Step 7: Run a gsy-e simulation

Activate the gsy-e environment:

```
source /home/vagrant/envs/gsy-e/bin/activate
```

Run simulation with:

```
cd /vagrant/gsy-e
gsy-e run
```

###Step 8: Run the Grid Singularity Exchange SDK in Vagrant

Activate the Exchange SDK environment:

```
source /home/vagrant/envs/exchange-sdk/bin/activate
```

To run your SDK script, run the following command (template here):

```
python your_sdk_script.py
```
