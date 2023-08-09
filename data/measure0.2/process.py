#%%
import os 
import re

dir_list = os.listdir()

#%%
def process_file(file):
    ans = []
    temp = None
    with open(file, 'r') as f:
        temp = f.readlines()
        # print(temp[3:])
    for line in temp[3:]:
        target = re.search('time=(.*) ms', line)#.group(1)
        if target:
            delay = float(target.group(1))
            ans .append(delay)
    return ans

# process_file(r'2_2/aupf2dn.txt')

# %%
all_data = {'pre':{}, 'next':{}, 'all':{}}
for d in dir_list:
    if os.path.isdir(d):
        pre, next = map(int, d.split('_'))
        all_data['pre'][(pre, next)] = process_file(os.path.join(d, 'ran2iupf.txt'))
        all_data['next'][(pre, next)] = process_file(os.path.join(d, 'aupf2dn.txt'))
        all_data['all'][(pre, next)] = process_file(os.path.join(d, 'ue2dn.txt'))
print(all_data)


#%%
ave_delay = {'pre':{}, 'next':{}, 'all':{}}
for k in all_data['pre'].keys():
    ave_delay['pre'][k] = sum(all_data['pre'][k])/len(all_data['pre'][k])
    ave_delay['next'][k] = sum(all_data['next'][k])/len(all_data['next'][k])
    ave_delay['all'][k] = sum(all_data['all'][k])/len(all_data['all'][k])
len(ave_delay['pre'])




# %%
