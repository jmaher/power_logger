from boto.s3.connection import S3Connection
from boto.s3.key import Key
import datetime

def upload_to_s3(unique_key):
    username = "eideticker"
    access_id = ""
    secret_key = ""
    bucket_name = "test-ateam-mozilla"

    conn = S3Connection(aws_access_key_id=access_id, 
                             aws_secret_access_key=secret_key)

    try:
        bucket = conn.get_bucket(bucket_name)
    except:
        bucket = conn.create_bucket(bucket_name)

    k = Key(bucket)
    k.key = '%s-power_report.csv' % unique_key
    k.set_contents_from_filename('report.csv')

if __name__ == "__main__":
    upload_to_s3('latest')

    today = datetime.datetime.today()
    d = "%s-%s-%s" % (today.year, today.strftime('%m'), today.strftime('%d'))
    upload_to_s3(d)
