import os

import numpy as np
import pandas as pd
import csv

CDF_x = '2'


def process_data_dynamic(df):
    # Identify the columns to process (all columns excluding the specified metadata columns)
    cols_to_process = df.columns.difference(
        ['HashOwner', 'HashApp', 'HashFunction', 'AverageAllocatedMb', 'AverageDurations'])

    df['invocations'] = df[CDF_x].astype(int)

    # Step 1 and 2: Multiply these columns with AverageDurations, divide by 1000, divide by 60, and round up
    for col in cols_to_process:
        df[col] = np.ceil(df[col] * df['AverageDurations'] / 1000 / 60).astype(int)

    # Step 3: Sum each column and output
    sums = df[cols_to_process].sum().tolist()

    # Step 4: Count values greater than 0 in each column and output
    counts = (df[cols_to_process] > 0).sum().tolist()

    # Step 5: Set values greater than 16 to 16, sum each column and output
    capped_sums_ = df[cols_to_process].map(lambda x: min(x, 8)).sum().tolist()

    # Step 5: Set values greater than 16 to 16, sum each column and output
    capped_sums = df[cols_to_process].map(lambda x: min(x, 16)).sum().tolist()

    grouped_df = df.groupby(CDF_x)['invocations'].sum().reset_index()
    grouped_df['CDF'] = grouped_df['invocations'].cumsum() / grouped_df['invocations'].sum()

    df[CDF_x + "_16"] = np.ceil(df[CDF_x] / 16).astype(int)
    df[CDF_x + "_8"] = np.ceil(df[CDF_x] / 8).astype(int)

    grouped_df_8 = df.groupby(CDF_x + "_8")['invocations'].sum().reset_index()
    grouped_df_8['CDF'] = grouped_df_8['invocations'].cumsum() / grouped_df_8['invocations'].sum()

    grouped_df_16 = df.groupby(CDF_x + "_16")['invocations'].sum().reset_index()
    grouped_df_16['CDF'] = grouped_df_16['invocations'].cumsum() / grouped_df_16['invocations'].sum()

    return [sums, counts, capped_sums_, capped_sums], grouped_df, grouped_df_8, grouped_df_16


if __name__ == '__main__':
    # 读取本地CSV文件
    df = pd.read_csv('merged_data.csv')
    result, grouped_df, grouped_df_8, grouped_df_16 = process_data_dynamic(df)

    result_dir = "statistics/vm-counts"
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    # Writing data to a CSV file
    with open(os.path.join(result_dir, "statistics.csv"), mode='w', newline='') as file:
        writer = csv.writer(file)
        for row in result:
            writer.writerow(row)

    # 计算累计频率
    grouped_df.to_csv(os.path.join(result_dir, "CDF-1.csv"), index=False)
    grouped_df_8.to_csv(os.path.join(result_dir, "CDF-8.csv"), index=False)
    grouped_df_16.to_csv(os.path.join(result_dir, "CDF-16.csv"), index=False)
