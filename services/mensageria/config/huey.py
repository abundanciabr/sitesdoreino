# config/huey.py  # [RECEITA:R8 v1]
import os

from huey import RedisHuey

huey = RedisHuey(url=os.environ["HUEY_REDIS_URL"])
