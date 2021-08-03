import os
import time
from datetime import datetime
import subprocess
import xlwt
import json

if __name__ == '__main__':
    start_time = time.time()
    datas = ["createTime", "isSuccess", "output", "error"]
    all_test_times = 100
    success_times = 0
    fail_times = 0
    for i in range(all_test_times):
        try:
            out_put = subprocess.check_output(["python", "./panophoto.py"])
            print("stress test {} times,output: {}".format(i, out_put))
            success_times += 1
            datas.append(([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "Yes",
                out_put,
                ""
            ]))
        except subprocess.CalledProcessError as e:
            out_put = e.output  # Output generated before error
            code = e.returncode  # Return code
            print("stress test {} times,output: {}".format(i, out_put))
            fail_times += 1
            datas.append(([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "Yes",
                out_put,
                code
            ]))
        except Exception as e:
            print("stress test {} times,output: {}".format(i, str(e)))
    
    print("Passing rate is {}%".format(float(success_times / all_test_times)))
    
    with open("datas{}.json".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')), "w") as f:
        json.dump(fp=f, obj=datas)
    
    workbook = xlwt.Workbook(encoding='utf-8')
    sheet = workbook.add_sheet('Worksheet')
    columns = ["createTime", "", ""]
    # 写入标题
    for col, column in enumerate(columns):
        sheet.write(0, col, column)
    # 写入每一行
    for row, data in enumerate(datas):
        for col, column_data in enumerate(data):
            sheet.write(row + 1, col, column_data)
    
    workbook.save('./TestReport{}.xls'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')))
