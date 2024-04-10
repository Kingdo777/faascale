import os

import pandas as pd
import numpy as np


def cold_start():
    # Load the CSV file
    df = pd.read_csv('merged_data.csv')

    cols_to_process = df.columns.difference(
        ['HashOwner', 'HashApp', 'HashFunction', 'AverageAllocatedMb', 'AverageDurations'])

    # Step 1: Calculate the minimum number of containers needed per minute.
    minute_columns = df[cols_to_process]  # Adjust based on your data
    container_df = df[['HashFunction']].copy()
    for minute in minute_columns:
        container_df[minute] = np.ceil(minute_columns[minute] * df['AverageDurations'] / 1000 / 60).astype(int)

    cold_start_1min_df = df[['HashFunction']].copy()
    cold_start_1min_vertical_df = cold_start_1min_df.copy()
    for minute in minute_columns:
        if minute == '1':
            continue
        else:
            cold_start_1min_df[minute] = np.maximum(container_df[minute] - container_df[str(int(minute) - 1)], 0)
            cold_start_1min_vertical_df[minute] = (
                    (container_df[minute] > 0) & (container_df[str(int(minute) - 1)] == 0)).astype(int)
    cold_start_1min_df['1'] = cold_start_1min_df[cold_start_1min_df.columns.difference(['HashFunction', '1'])].sum(
        axis="columns")
    cold_start_1min_vertical_df['1'] = cold_start_1min_vertical_df[
        cold_start_1min_vertical_df.columns.difference(['HashFunction', '1'])].sum(
        axis="columns")

    cold_start_10min_df = df[['HashFunction']].copy()
    cold_start_10min_vertical_df = cold_start_10min_df.copy()
    for minute in minute_columns:
        if minute == '1':
            continue
        else:
            warm_list = [str(i) for i in range(max(1, int(minute) - 10), int(minute))]
            cold_start_10min_df[minute] = np.maximum(container_df[minute] - container_df[warm_list].max(axis=1), 0)
            cold_start_10min_vertical_df[minute] = (
                    (container_df[minute] > 0) & (container_df[warm_list].max(axis=1) == 0)).astype(int)
    cold_start_10min_df['1'] = cold_start_10min_df[cold_start_10min_df.columns.difference(['HashFunction', '1'])].sum(
        axis="columns")
    cold_start_10min_vertical_df['1'] = cold_start_10min_vertical_df[cold_start_10min_vertical_df.columns.difference(
        ['HashFunction', '1'])].sum(
        axis="columns")

    cold_start_60min_df = df[['HashFunction']].copy()
    cold_start_60min_vertical_df = cold_start_60min_df.copy()
    for minute in minute_columns:
        if minute in [str(i) for i in range(1, 61)]:
            continue
        else:
            warm_list = [str(i) for i in range(max(1, int(minute) - 60), int(minute))]
            cold_start_60min_df[minute] = np.maximum(container_df[minute] - container_df[warm_list].max(axis=1), 0)
            cold_start_60min_vertical_df[minute] = (
                    (container_df[minute] > 0) & (container_df[warm_list].max(axis=1) == 0)).astype(int)
    cold_start_60min_df['1'] = cold_start_60min_df[cold_start_60min_df.columns.difference(['HashFunction', '1'])].sum(
        axis="columns")
    cold_start_60min_vertical_df['1'] = cold_start_60min_vertical_df[cold_start_60min_vertical_df.columns.difference(
        ['HashFunction', '1'])].sum(
        axis="columns")

    print(cold_start_1min_df['1'].sum(), cold_start_1min_vertical_df['1'].sum(), cold_start_10min_df['1'].sum(),
          cold_start_10min_vertical_df['1'].sum(), cold_start_60min_df['1'].sum(),
          cold_start_60min_vertical_df['1'].sum())

    return [cold_start_1min_df, cold_start_1min_vertical_df, cold_start_10min_df, cold_start_10min_vertical_df,
            cold_start_60min_df, cold_start_60min_vertical_df]


def save_to_csv(df, filename):
    df.to_csv(filename, index=False)


if __name__ == '__main__':
    result_dir = "statistics/cold-start-counts"
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    results = cold_start()
    save_to_csv(results[0], os.path.join(result_dir, "1min_horizontal.csv"))
    save_to_csv(results[1], os.path.join(result_dir, "1min_vertical.csv"))
    save_to_csv(results[2], os.path.join(result_dir, "10min_horizontal.csv"))
    save_to_csv(results[3], os.path.join(result_dir, "10min_vertical.csv"))
    save_to_csv(results[4], os.path.join(result_dir, "60min_horizontal.csv"))
    save_to_csv(results[5], os.path.join(result_dir, "60min_vertical.csv"))
