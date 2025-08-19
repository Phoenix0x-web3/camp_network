# Phoenix Dev

More info:  
[Telegram Channel](https://t.me/phoenix_w3)  
[Telegram Chat](https://t.me/phoenix_w3_space)

## Camp Network Network

Camp Network is an Layer-1 blockchain currently in Testnet Phase 3, designed to register, protect, and monetize intellectual property directly on-chain.

## Functionality
- Faucet
- Twitter quests
- On-chain quests

## Requirements
- Python version 3.11 - 3.12 
- Private keys for EVM wallets
- Proxy (optional)
- Twitter auth tokens (optional) 
- Discord auth tokens (optional)
- Refferal codes (optional)
- Telegram token for logs (optional) 

## Installation
1. Clone the repository:
```
git clone https://github.com/Phoenix0x-web3/camp_network.git
cd camp_network
```

2. Install dependencies:
```
python install.py
```

3. Activate virtual environment:
```
venv\Scripts\activate
```

4. Run script
```
python main.py
```

## Project Structure
```
camp_network/
├── data/                   #Web3 interface
├── files/
|   ├── discord_tokens.txt  # Discord auth tokens (optional)
|   ├── twitter_tokens.txt  # Twitter auth tokens (optional)
|   ├── reserve_twitter.txt # Reserved Twitter auth tokens, in case the main twitter tokens becomes unavailable  (optional)
│   ├── private_keys.txt    # EVM wallet private keys
|   ├── proxy.txt           # Proxy addresses (optional)
|   ├── reserve_proxy.txt   # Reserved Proxy addresses for usage, in case the main proxy becomes unavailable (optional)
|   ├── ref_codes.txt       # List of refferals codes (optional)
|   ├── wallets.db          # Database. Use SQLite(https://sqlitebrowser.org/) for easy and convenient opening of your data.
│   └── settings.yaml       # Main configuration file
├── functions/              # Functionality
└── utils/                  # Utils
```
## Configuration

### 1. files folder
- `private_keys.txt`: One private key per line
- `proxy.txt`: One proxy per line (format: `http://user:pass@ip:port`)
- `reserve_proxy.txt`: One proxy per line (format: `http://user:pass@ip:port`)
- `twitter_tokens.txt`: One token per line 
- `reserve_twitter.txt`: One token per line 
- `discord_tokens.txt`: One token per line 
- `ref_codes.txt`: One code per line 

### 2. Main configurations
```yaml
# Whether to encrypt private keys
private_key_encryption: true

# Number of threads to use for processing wallets
threads: 1

# Number of retries for failed action
retry: 3

# BY DEFAULT: [] - all wallets
# Example: [1, 3, 8] - will run only 1, 3 and 8 wallets
exact_wallets_to_run: []

# Whether to shuffle the list of wallets before processing
shuffle_wallets: true

# Hide wallet address in logs
hide_wallet_address_log: true

# the log level for the application. Options: DEBUG, INFO, WARNING, ERROR
log_level: INFO

# Random pause for start wallet in any modules
random_pause_start_wallet:
  min: 0
  max: 0

# Random pause between actions in seconds
random_pause_between_actions:
  min: 20
  max: 30

# Telegram Bot ID for notifications
tg_bot_id: ''

# You can find your chat ID by messaging @userinfobot or using https://web.telegram.org/. (example 1540239116)
tg_user_id: ''
```

### 3. Module Configurations

**Settings**:
```yaml
# Actual Windows UserAgent. If capmonster can't resolve captcha. Try update Chrome version. 138.0.0.0 -> 139.0.0.0
actual_ua: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, 
  like Gecko) Chrome/138.0.0.0 Safari/537.36
# Api Key from https://dash.capmonster.cloud/
capmonster_api_key: 10**************************
# SolveCaptcha Api Key. Used for faucet
solvecaptcha_api_key: 34******************************
#Use referral code for login
use_ref_code: true
#Use ref code only from files/ref_codes.txt. If false script will take codes form your Data Base
use_only_file_ref_code: false
#Perform automatic replacement from proxy reserve files
auto_replace_proxy: true
#Perform automatic replacement from twitter reserve files
auto_replace_twitter: false
#Maximum possible number of errors before replacement
resources_max_failures: 3
# Random pause between twitter actions in seconds
random_pause_between_twitter_actions:
  min: 200
  max: 600
```
**Onchain quests**:
```yaml
#Actions for onchain quests
onchain_actions: [base_camp, aura, sticky_pleb, climb, pictographs, tokentails, 
      omnihub_mint, tavern_quest, mintpad, bleetz, chainbills, conft, copass, 
      mysphere, storychain]
#Multiple actions for onchain. Example mint one type NFT > 1 times. 
mulitple_actions: false
#Use faucet if wallet balance > 0
use_faucet_if_balance: false
#Name quest for logger. Ids quest for complete
quests_name_and_ids: {CampOrigin: 2585eb2f-7cac-45d1-88db-13608762bf17, 
    TrailHeadsSpotify: 45d34ce3-b6f8-446e-9460-0f35ef20a3c5, TokenTailsTG: 
    06b0d411-c1df-4cc5-a72c-e47dc911a0b3, StoryChainDS: 
    4345ec66-0746-4a77-85d0-a79db42612b1, StoryChainCheck: 
    541ff274-95c5-409a-9ea2-c80ec2719d7e, CoLab: 
    54461745-809e-4387-a732-a86199629a54, DmailTG: 
    b635cbca-a42b-41df-a64d-a2103d4cb1d4, Dmail: 
    0d9b5216-1b06-4a54-baa6-1cbd40ff132d, MySphereDS: 
    148eeb88-00bf-465a-a69c-94b350ef9570, MySphereCreateAcc: 
    78508cb6-0141-4500-a6b0-530f2428a289, Olympics: 
    467345fc-ec7c-4889-b053-bd93005b2636, RapierDS: 
    8257294c-db65-46f8-8a0b-74351705f49f, RapierPlay: 
    dff8e739-6323-4d4e-bf1b-67aa7d7eb251, XadeTG: 
    d3776b9a-dba9-4553-92c5-73421ea9cced, ScorePlayDS: 
    e7c0f882-82b7-499e-8a05-40528e0047ee, SummitXDS: 
    3dfca204-edf2-461a-8fda-4067b09241a7, SummitXTG: 
    861e2917-3725-48ba-b8b9-4466cd81fe72, SummitXCheck: 
    211c9b79-ff65-42f8-a59a-ad0539129aa9, ArcoinTG: 
    aa08b2a5-eaab-469c-9e6f-e3a380c23faa, BleetzCreate: 
    10668db1-081d-40e2-9f42-06fafc67e4aa, KraftDS: 
    f4de4fa8-ad5c-45c9-a804-0483309de9f9, PanenkaTG: 
    be50eaa0-945a-4664-8d07-a2f02167cf38, PictographsTG: 
    2233dcaa-a2be-49fb-b322-28bf9d387475, PictographsTGBot: 
    2ba6c29a-69a1-4ff8-ac61-f4b19431f8d2, PixudiTG: 
    9f8edb41-4867-48e0-8d7a-8437c2c6e1b1, RewardedTV: 
    d7a3a18b-38fd-45d5-937a-f974dff403bd, CristalCreate: 
    d4fdee29-c60f-40f2-8795-1da0e9e5414e, BelgranoCreate: 
    e6eda663-977e-4d71-a03c-a1020db88064, AwanaDs: 
    8c04ae85-3e7a-471a-b79b-ec976c513f47, AwanaTG: 
    9b87193e-c568-4a72-915d-1bdba060b00e, Clusters: 
    3ea83621-0087-4fc1-9967-c21265e2c369, JukeBloxTG: 
    46a1b202-ab7b-4c29-bf13-417c6a8267af, ChainbilssTG: 
    3bdf21b6-724b-419a-998a-2492b926ce23, ChainbilssDS: 
    d3006d57-a273-4827-a81b-fe1f27f905ca, HighNoon: 
    70c4ca65-b981-4b83-8d31-434107389e17, HighNoonDS: 
    bed30ac7-5b01-44fe-880b-68f27c3af0ea, BlackMirrorTG: 
    5494bd75-8737-4b52-80de-1e20ae4d9ec5, KorProtocolTG: 
    e5a0beb8-3df2-4284-bc85-9dc1e08fd675, LastMonarchy: 
    a969d309-1aa8-4423-9902-a7d1afee0f6b, MintPad: 
    1e203cd9-f639-4b54-a68c-8a3131321239, MintPadDS: 
    0b4aac39-e4f7-4ce5-a591-7a9481eb0d81, OmniHubNFT: 
    6ab52aa8-edfc-4890-8c8b-62d479cb40d6, PlenaTG: 
    332b56cd-d85d-41d1-87b9-d2200d5f994e, PlenaDS: 
    757f9546-e431-4a8d-9934-a93b1dcf5bbe, RemasterMarketPlace: 
    2109ea82-5cad-4c38-af6b-209db82188d2, RupturelabsTG: 
    760e5ae4-16a9-44a1-9e3f-cd6a62a76a10, RupturelabsDS: 
    c7f504bc-bb29-44a2-ac42-df9ce74bdf7b}
```

**Twitter quests**:
```yaml
#Twitter quests
quests_twitter: {Follow: {campnetworkeco: d77591f0-1e0b-4136-91a9-dcfe9b9490e1, 
      campnetworkxyz: 2660f24a-e3ac-4093-8c16-7ae718c00731, WEARETRaiLHEADS: 
      deadebb4-dc7e-4c49-b852-9f533ff84961, ativ_official: 
      90d9fe50-75b5-4168-be7d-088eea19a566, chainbills_xyz: 
      8f41af8b-938f-46d9-a67a-2f00f4749ac9, rgbclash_xyz: 
      d507bf9f-55d2-4c10-b3a1-0e6d256dd5de, PlayFlappyTrump: 
      5967d66d-1efa-477a-951e-fb112bd76489, 0xhighnoon: 
      108bd991-fcbf-4653-a947-90f401ad8fb7, relicquest: 
      eab0fcc5-a0a3-46e5-9d04-4e1187e8ff35, blackmirror_xp: 
      cff992ff-d4a5-4eac-b41f-82062d4371d6, korprotocol: 
      4ad94eee-85bb-45ee-bc36-f87521a5dca2, mighty_study: 
      3c967701-d023-46ff-b75e-c09c4f3d4d8a, mintpadco: 
      60787d92-3316-4ae2-a780-d211fb2247e4, Omni_Hub: 
      23275d3c-e177-4ebc-91d1-f6f51be3ff31, PlenaFinance: 
      d2d126d3-c7a9-4b2f-a955-bc94dec405ec, rupturelabs: 
      2c7e19b1-b60e-4733-b185-3ee0d6cc232d, HairyLabs: 
      1e158437-b9b7-45ac-87d7-90cc64d4ea03, ChikoGames_: 
      58168ac6-bb8b-4c34-bd17-6ecab049d094}}
```

## Usage

For your security, you can enable private key encryption by setting private_key_encryption: true in the settings. If set to false, encryption will be skipped.

On first use, you need to fill in the `private_keys.txt` file once. After launching the program, go to `DB Actions → Import wallets to Database`. Also if you have encrypted private keys from previous projects you can paste them to file, you don't need to use pure private keys. But you need to remeber your password.

<img src="https://imgur.com/BgajX57.png" alt="Preview" width="600"/>


<img src="https://imgur.com/KZ5tyRK.png" alt="Preview" width="600"/>


If encryption is enabled, you will be prompted to enter and confirm a password. Once completed, your private keys will be deleted from the `private_keys.txt` file and securely moved to a local database, which is created in the `files` folder.

<img src="https://imgur.com/2J87b4E.png" alt="Preview" width="600"/>

If you want to update proxy or twitter/discord tokens you need to make synchronize with DB. After you made changes in files `proxy.txt`, `twitter_tokens.txt` or `discord_tokens.txt`, please choose this option.

<img src="https://imgur.com/BiGswZU.png" alt="Preview" width="600"/>

Once the database is created, you can start the project by selecting `Camp Network → Complete Twitter and Regular Quests`.

<img src="https://imgur.com/6LX3Sfu.png" alt="Preview" width="600"/>

```yaml 
Complete Twitter and Regular Quests #run all quests in random order
Complete Regular Quests #complete only regular quests 
Complete Twitter Quests #complete only twitter quests 
Complete Onchain and Faucet #complete oncahin quests and faucet
Complete Faucet #Faucet
Update Points #Calculate points

```

To decrypt the private keys, enter the password.
<img src="https://imgur.com/RahNzya.png" alt="Preview" width="600"/>


