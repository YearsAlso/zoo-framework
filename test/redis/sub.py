import time

import redis

redis_conn = redis.Redis(host='localhost', port=6379, decode_responses=True)

p = redis_conn.pubsub()
p.subscribe("codehole")

time.sleep(1)
while True:
    print(p.get_message())