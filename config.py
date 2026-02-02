import os

class Config:
    SECRET_KEY = "supersecretkey"
    SQLALCHEMY_DATABASE_URI = "sqlite:///database.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    #custodial deposit addresses (set them here)
    #Users will see these as their "deposit address" in the UI.
    DEPOSIT_ADDRESSES = {
        "USDT": {
            "TRC20": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "ERC20": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "BEP20": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "POLYGON": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "ARBITRUM": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "OPTIMISM": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "SOL": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
        },
        "USDC": {
            "ERC20": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "BEP20": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "POLYGON": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "ARBITRUM": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "OPTIMISM": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "SOL": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
        },
        "CAD": {
            "INTERAC": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "SWIFT": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "WIRE": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf"
        },
        "BTC": {
            "BTC": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf"
        },
        "ETH": {
            "ETH": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "ARBITRUM": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
            "OPTIMISM": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf",
        },
        "BNB": {
            "BEP20": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf"
        },
        "SOL": {
            "SOL": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf"
        },
        "XRP": {
            "XRP": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf"
        },
        "TRX": {
            "TRC20": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf"
        },
        "LTC": {
            "LTC": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf"
        },
        "DOGE": {
            "DOGE": "1JxTb84bvE44A9j7ZySmMxJSbG5ovwb2Jf"
        },
    }




