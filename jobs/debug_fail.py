from redis import Redis
from rq import Queue
from rq.registry import FailedJobRegistry

redis_conn = Redis.from_url("redis://default:dwlcQPqxLOQ9IOaHGzwffLZqP4gRSflS@zippy-hand-kitty-56703.db.redis.io:18170")
queue = Queue(connection=redis_conn)

failed_registry = FailedJobRegistry(queue=queue)

for job_id in failed_registry.get_job_ids():
    job = queue.fetch_job(job_id)
    print("JOB ID:", job_id)
    print("FUNC:", job.func_name)
    print("ARGS:", job.args)
    print("ERROR:\n", job.exc_info)
    print("=" * 50)