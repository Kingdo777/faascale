sudo chown kingdo /tmp/qmp.sock
sudo chgrp kingdo /tmp/qmp.sock
sudo killall -9 gunicorn

gunicorn --bind :8081 --workers 1 --threads 8 --timeout 0 app:app