Following are the prequisite to run D3A on tobalaba:

- Please install [Parity client](https://github.com/paritytech/homebrew-paritytech).

- Open your terminal and launch the tobalaba node with:

  `parity --chain tobalaba --jsonrpc-apis=all --jsonrpc-cors=all`

- Goto `/Users/<user>/Library/Application Support/io.parity.ethereum/keys` and overwrite [Tobalaba.zip](https://gridsingularity.atlassian.net/wiki/download/attachments/787251201/Tobalaba.zip?version=1&modificationDate=1540482999613&cacheVersion=1&api=v2) after unzipping it (PS: Do backup your already existing keys, if you need them later).

Launch the simulation on tobalaba via cli:

```
d3a -l INFO run -t 15s -s 60m -m 1 --enable-bc --setup tobalaba.<setup_file_name>
```