import time

import redis

redis_conn = redis.Redis(host='localhost', port=6379, decode_responses=True)

if __name__ == '__main__':
    redis_conn.zadd("ztest", {"message": int(time.time() * 1000)})
