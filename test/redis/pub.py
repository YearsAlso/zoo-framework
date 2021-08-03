import time

import redis

redis_conn = redis.Redis(host='localhost', port=6379, decode_responses=True)

if __name__ == '__main__':
    while True:
        time.sleep(2)
        redis_conn.publish("ELS_SURFACE_FRONT_MSG", "Test")
