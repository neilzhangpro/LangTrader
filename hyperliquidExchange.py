import json
from utils import logger
from hyperliquid.info import Info
from hyperliquid.utils import constants
from hyperliquid.exchange import Exchange
import eth_account
from eth_account.signers.local import LocalAccount


class hyperliquidAPI:
    """ This class is used to interact with the hyperliquid API"""
    def __init__(self, config_path:str = "config.json"):
        #loading config
        with open(config_path,"r") as f:
            config = json.load(f)
        self.account_address = config["account_address"]
        self.secret_key = config["secret_key"]
        self.account:LocalAccount = eth_account.Account.from_key(self.secret_key)
        #ues mainnet api
        self.info = Info(constants.MAINNET_API_URL, skip_ws=True)
        #use testnet api
        #self.info_testnet = Info(constants.TESTNET_API_URL, skip_ws=True)
        self.contract_balance = self.get_account_balance()
        self.spot_balance = self.get_account_balance()
        #init exchange
        self.exchange = Exchange(
            self.account,
            base_url=constants.MAINNET_API_URL,
            account_address=self.account_address,
            perp_dexs=None
        )
        self.contract_positions = []

    def get_account_balance(self):
        """Get the accound balance of the account"""
        try:
            #contract balance
            user_state = self.info.user_state(self.account_address)
            logger.info(f"Contract account balance: {user_state}")
            self.contract_balance = user_state
            #spot balance
            spot_user_state = self.info.spot_user_state(self.account_address)
            logger.info(f"Spot account balance: {spot_user_state}")
            self.spot_balance = spot_user_state
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return None
    

    def calculate_buy_size(self,coin_name:str,leverage:int = 1):
        """Calculate the buy size"""
        #should update the balance anyway
        self.contract_balance = self.get_account_balance()
        self.spot_balance = self.get_account_balance()
        infomation = {}
        try:
            meta = self.info.meta()
            all_mids = self.info.all_mids()
            coin_price = float(all_mids.get(coin_name, 0))
            if coin_price == 0:
                ValueError(f"There is no price for {coin_name}");
            logger.info(f"Current {coin_name} price is {coin_price}")
            withdrawable = float(self.contract_balance["marginSummary"]["totalRawUsd"])
            max_buy_size = (withdrawable * leverage) / coin_price
            max_buy_size = round(max_buy_size,3)
            logger.info(f"Withdrawable amount is {withdrawable}")
            logger.info(f"Max buy size for {coin_name} is {max_buy_size}")
            if max_buy_size < 0.001: #min order size
                logger.info("account balance is insufficent for buying")
                return None
            
            infomation["coin_name"] = coin_name
            infomation["leverage"] = leverage
            infomation["coin_price"] = coin_price
            infomation["max_buy_size"] = max_buy_size
            return infomation
        except Exception as e:
            logger.error(f"Error calculating buy size: {e}")
            return None
    def test_order(self,coin_name:str):
        """Set a test order"""
        try:
            #calculate the buy size
            coin_name = coin_name.upper()
            leverage = 5
            #set leverage
            logger.info(f"Setting leverage to {leverage}")
            leverage_result = self.exchange.update_leverage(
                leverage,
                coin_name,
                True, # use cross margin
            )
            logger.info(f"Leverage result: {leverage_result}")
            #calculate the buy size
            buy_size = self.calculate_buy_size(coin_name,5)
            if buy_size is None:
                logger.info("Insufficent balance for buying")
                return None
            logger.info(f"Buying {buy_size['max_buy_size']} {buy_size['coin_name']} with leverage {buy_size['leverage']}")
            #use the market order
            order_result = self.exchange.market_open(
                coin_name,
                True,
                buy_size["max_buy_size"],
                None,
                0.01
            )
            logger.info(f"Test order result: {order_result}")
            return order_result
        except Exception as e:
            logger.error(f"Error setting test order: {e}")
            return None
    
    def close_all_positions(self,order_type:str = "market", limit_price_offset: float = 0.5,limit_price:float = None, tif: str="Gtc"):
        """
        Close all postions
        Args:
            order_type: str = "market",
            limit_price_offset: float = 0.5,
            limit_price: float = None,
            tif: str="Gtc"
                - "Gtc": until the order is executed
                - "Ioc": immediate or cancel
                - "Alo": Add liquidity only
        """
        #should update the balance anyway
        self.contract_balance = self.get_account_balance()
        self.spot_balance = self.get_account_balance()
        try:
            #get all postion
            postions = self.contract_balance["assetPositions"]
            if not postions:
                logger.info("No postions to close")
                return
            
            logger.info(f"Closing {len(postions)} positions")
            logger.info(f"Preparing to {'limit' if order_type == 'limit' else 'market'} order with {limit_price_offset} offset and {tif} tif")

            #get limit price
            all_mids = self.info.all_mids() if order_type == "limit" else {}

            for position in postions:
                pos = position.get("position",{})
                coin = pos.get("coin")
                szi = float(pos.get("szi","0"))
                size = abs(szi)

                if size == 0:
                    logger.info(f"Position {coin} is already closed")
                    continue

                #judge long or short position
                is_long = szi > 0
                
                logger.info(f"Closing {coin} position with size {size}")
                 
                if order_type == "market":
                    #close by market order
                    result = self.exchange.market_close(
                        coin,
                        size,
                        slippage=0.01
                    )
                else:
                    #close by limit order
                    is_buy = not is_long
                    current_price = float(all_mids.get(coin,0))
                    if current_price == 0:
                        ValueError(f"There is no price for {coin}");
                        continue

                    if limit_price is not None:
                        final_price = limit_price
                        logger.info(f"Using provided limit price: {final_price}")
                    else:
                        #calulate the limit price
                        if is_long:
                            final_price = current_price * (1 - limit_price_offset / 100)
                        else:
                            final_price = current_price * (1 + limit_price_offset / 100)
                        final_price = round(final_price,3)
                        logger.info(f"Limit price for {coin} is {final_price}")
                    result = self.exchange.order(
                        coin,
                        is_buy,
                        size,
                        final_price,
                        {"limit":{"tif":tif}},
                        reduce_only=True
                    )
                logger.info(f"Closed result: {result}")
            
            return True
        except Exception as e:
            logger.error(f"⚠️ Error closing positions: {e}")
            return None
    

    def _get_asset_index(self,coin_name:str):
        """Get the index of universe """
        try:
            meta = self.info.meta()
            universa = meta.get("universe",[])

            for idx, asset in enumerate(universa):
                if asset.get("name") == coin_name:
                    return idx
            
            raise ValueError(f"Asset {coin_name} not found in universe")
        except Exception as e:
            logger.error(f"Error getting asset index: {e}")
            return None