Files can be uploaded to generate custom energy supply or load profiles. The following file formats are supported:

##Comma Separated Values (.csv)

The separation can be done by comma `,` or semicolon `;`. Two time formats are supported, see below. Power set-points are given in **Watts**. The software handles any conversions to energy (in kWh).

###hh:mm

**Example:**

```
INTERVAL;POWER(W):
00:00;10
00:15;10
00:30;10
00:45;10
01:00;10
```

###YYYY-MM-DDThh:mm

**Example:**

```
INTERVAL,POWER(W)
2019-01-01T00:00,10.0
2019-01-01T00:15,10.0
2019-01-01T00:30,10.0
2019-01-01T00:45,10.0
2019-01-01T01:00,10.0
```

Note: If you upload csv files with date information, the **start-date** of the simulation should be identical in the csv files and [simulation settings](general-settings.md).
