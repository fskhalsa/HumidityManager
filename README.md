# HumidityManager
Python script for managing reptile vivarium humidity using SensorPush humidity sensors and VeSync smart outlets

## Setup

```
$ pip install -r requirements.txt
$ npm install pm2 -g
$ pm2 start humidity-manager.py --name "Humidity Manager" --interpreter python3
```