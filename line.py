from tqdm import tqdm
import time

# # 基本用法
# for i in tqdm(range(100)):
#     time.sleep(0.1)  # 模拟任务

# 带描述的进度条
with tqdm(range(100), desc="处理进度") as pbar:
    for i in pbar:
        time.sleep(0.1)
       
# # 手动更新
# pbar = tqdm(total=100)
# for i in range(10):
#     time.sleep(0.5)
#     pbar.update(10)  # 每次更新10
# pbar.close()