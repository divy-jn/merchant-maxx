import yaml

d = {}
with open('.env', 'r') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            d[k] = v.strip('"\'')
            
# add the CORS_ORIGINS as well
d['CORS_ORIGINS'] = 'http://localhost:5173,https://merchant-maxx.vercel.app'

with open('env_deploy_new.yaml', 'w') as f:
    yaml.dump(d, f)
