import os
for root, _, files in os.walk('backend'):
    for file in files:
        if file.endswith('.py'):
            fp = os.path.join(root, file)
            with open(fp, 'r', encoding='utf-8') as f:
                c = f.read()
            # Replace escaped \'data\'
            nc = c.replace("\\'data\\'", '"data"')
            if nc != c:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(nc)
                print('Fixed', fp)
