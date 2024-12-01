# -*- coding: utf-8 -*-
"""preprocessing.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1tucmFOSJtrJX2FrQAP-_1yC2dq_MMhkV
"""

import pandas as pd
import os
import glob
import logging

# 경로 설정
LOG_DIR = os.path.join(os.getcwd(), "preprocessing", "preprocessing_logs")  # 로그 폴더
LOG_FILE = os.path.join(LOG_DIR, "preprocessing.log")  # 로그 파일 경로
DATA_DIR = os.path.join(os.getcwd(), "acquisition", "data")  # 데이터 폴더
OUTPUT_DIR = os.path.join(os.getcwd(), "preprocessing", "preprocessed_data")  # 출력 폴더

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",  # 인코딩 설정
)

# 1. 데이터 로드 함수
def load_all_data():
    parquet_files = glob.glob(os.path.join(DATA_DIR, "*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No Parquet files found in directory: {DATA_DIR}")

    logging.info(f"발견된 Parquet 파일: {parquet_files}")
    # 모든 Parquet 파일 로드 및 병합
    dataframes = [pd.read_parquet(file) for file in parquet_files]
    combined_data = pd.concat(dataframes, ignore_index=True)
    logging.info(f"병합된 데이터 크기: {combined_data.shape}")

    return combined_data

# 2. 데이터 저장 함수
def save_data(data, output_name):
    os.makedirs(OUTPUT_DIR, exist_ok=True)  # 디렉토리가 없으면 생성
    output_path = os.path.join(OUTPUT_DIR, output_name)
    # 데이터 Parquet 형식으로 저장
    data.to_parquet(output_path, index=False, engine="pyarrow")
    logging.info(f"데이터 저장 완료: {output_path}")

# 3. 데이터 전처리 함수
def preprocess_data(data):
    """
    병합된 데이터의 전처리 작업을 수행합니다.
    """
    # 1. 컬럼명 정리
    logging.info("컬럼명 정리 중...")
    data.columns = data.columns.str.strip()  # 공백 제거
    logging.info(f"정리된 컬럼명: {list(data.columns)}")

    # 2. 삭제 대상 컬럼 제거
    columns_to_drop = ['지번부번지', '건물부번지', '동정보', '층정보', '호정보']
    data = data.drop(columns=columns_to_drop, errors='ignore')
    logging.info(f"삭제된 컬럼: {columns_to_drop}")

    # 3. 결측값 처리
    logging.info("결측값 처리 중...")
    data['지점명'] = data['지점명'].fillna('본점')  # 결측값 대체
    data['지번본번지'] = data['지번본번지'].fillna(0).astype(int)
    data['도로명코드'] = data['도로명코드'].fillna(0).astype(int)
    data['건물본번지'] = data['건물본번지'].fillna(0).astype(int)
    data['구우편번호'] = data['구우편번호'].fillna(0).astype(int)
    data = data.dropna(subset=['상호명', '표준산업분류코드', '표준산업분류명'])  # 특정 컬럼 결측값 제거
    logging.info("결측값 처리 완료")

    # 4. 중복 제거
    before_duplicates = data.shape[0]
    data = data.drop_duplicates(subset=['상가업소번호'])
    after_duplicates = data.shape[0]
    logging.info(f"중복 제거 완료: {before_duplicates - after_duplicates}개 중복 제거")

    # 5. 불필요한 컬럼 제거
    columns_to_drop = ['건물명', '건물관리번호', '구우편번호', '법정동코드', '행정동코드',
                       '지번코드', '대지구분코드', '도로명코드', '도로명', '건물본번지',
                       '지번본번지', '상가업소번호', '상권업종대분류코드', '상권업종중분류코드', '시도코드']
    data = data.drop(columns=columns_to_drop, errors='ignore')
    logging.info(f"불필요한 컬럼 제거 완료: {columns_to_drop}")

    # 6. 데이터 타입 변환
    logging.info("데이터 타입 변환 중...")
    data['경도'] = pd.to_numeric(data['경도'], errors='coerce')
    data['위도'] = pd.to_numeric(data['위도'], errors='coerce')
    logging.info(f"변환 후 데이터 타입:\n{data[['경도', '위도']].dtypes}")

    # 7. 데이터 유효성 확인 및 이상값 제거
    valid_longitude = (-180, 180)
    valid_latitude = (-90, 90)
    invalid_locations = data[
        (data['경도'] < valid_longitude[0]) | (data['경도'] > valid_longitude[1]) |
        (data['위도'] < valid_latitude[0]) | (data['위도'] > valid_latitude[1])
    ]
    logging.info(f"이상값 개수: {invalid_locations.shape[0]}")
    data = data[
        (data['경도'] >= valid_longitude[0]) & (data['경도'] <= valid_longitude[1]) &
        (data['위도'] >= valid_latitude[0]) & (data['위도'] <= valid_latitude[1])
    ]
    logging.info("유효하지 않은 위치 제거 완료")

    # 8. 상권 상태 분류
    def classify_location(latitude, longitude):
        """
        위도와 경도를 기준으로 상권 상태를 분류.
        중심상권: 위도 > 37.5, 경도 > 126.9
        기타: 위 조건에 해당하지 않는 지역
        """
        if latitude > 37.5 and longitude > 126.9:
            return '중심상권'
        return '기타'

    data['상권상태'] = data.apply(lambda x: classify_location(x['위도'], x['경도']), axis=1)
    logging.info("상권 상태 분류 완료")
    logging.info(f"상권 상태 분포:\n{data['상권상태'].value_counts()}")

    return data

# 메인 실행 함수
def main():
    try:
        # 데이터 로드 및 병합
        merged_data = load_all_data()
        # 데이터 전처리
        processed_data = preprocess_data(merged_data)
        # 전처리된 데이터 저장
        save_data(processed_data, "preprocessed_data.parquet")

    except Exception as e:
        logging.error(f"오류 발생: {e}")

if __name__ == "__main__":
    main()
