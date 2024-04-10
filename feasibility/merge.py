import pandas as pd


def merge_tables(df1, df2, df3):
    # 扩展表2以包含HashFunction信息
    df2_expanded = pd.merge(df1[['HashOwner', 'HashApp', 'HashFunction']], df2, on=['HashOwner', 'HashApp'], how='inner')
    # 合并扩展后的表2到表1
    df1_merged = pd.merge(df1, df2_expanded, on=['HashOwner', 'HashApp', 'HashFunction'], how='inner')
    # 合并表3到上面的合并表
    final_merged = pd.merge(df1_merged, df3, on=['HashOwner', 'HashApp', 'HashFunction'],
                            how='inner')  # 使用内连接确保只保留表3中存在的函数

    return final_merged


if __name__ == '__main__':
    file_name1 = 'data/invocations_per_function_md.anon.d01.csv'
    file_name2 = 'data/app_memory_percentiles.anon.d01.csv'
    file_name3 = 'data/function_durations_percentiles.anon.d01.csv'

    df1 = pd.read_csv(file_name1)
    df2 = pd.read_csv(file_name2)
    df3 = pd.read_csv(file_name3)

    final_df = merge_tables(df1, df2, df3)

    # 调整列顺序，使 AverageAllocatedMb 和 Average 在 HashFunction 之后
    columns = ['HashOwner', 'HashApp', 'HashFunction', 'AverageAllocatedMb', 'Average'] + [col for col in
                                                                                           final_df.columns if
                                                                                           col not in ['HashOwner',
                                                                                                       'HashApp',
                                                                                                       'HashFunction',
                                                                                                       'AverageAllocatedMb',
                                                                                                       'Average']]
    final_df = final_df[columns]

    # 重命名列
    final_df.rename(columns={'Average': 'AverageDurations'}, inplace=True)

    final_df.to_csv('./merged_data.csv', index=False)
