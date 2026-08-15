import os

import qlib
from qlib.contrib.model import LGBModel
from qlib.data.dataset import DatasetH
from qlib.workflow import R

qlib.init(provider_uri="~/.qlib/qlib_data/amz_data", region="cn")

if __name__ == '__main__':
    # etf_data = D.features(
    #     instruments=["SH518880"],
    #     fields=["$close", "$open", "$high", "$low", "$volume", "($close - $open) / $open",
    #             "($close - Ref($close , 1)) / Ref($close, 1)", "Mean($close, 5)", "Std($close, 5)", "Mean($volume, 5)",
    #             "Std($volume, 26)", "Mean($close, 26)", "Max($high, 20) / Min($low, 20)"],
    #     start_time="2019-01-01",
    #     end_time="2026-08-10",
    #     freq="day"
    # )
    # print(etf_data.head())

    os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

    handler_config = {
        "start_time": "2019-01-01",
        "end_time": "2026-08-10",
        "fit_start_time": "2010-01-01",
        "fit_end_time": "2026-08-10",
        "instruments": ["SH518880"],
        "infer_processors": [],

    }

    dataset = DatasetH(
        handler={
            "class": "Alpha158",
            "module_path": "qlib.contrib.data.handler",
            "kwargs": handler_config,
        },
        segments={
            "train": ("2010-01-01", "2020-12-31"),
            "valid": ("2021-01-01", "2021-12-31"),
            "test": ("2022-01-01", "2025-12-31"),
        }
    )

    model = LGBModel(
        eval_metric="rmse",
        colsample_bytree=0.8879,
        learning_rate=0.2,
        subsample=0.8789,
        lambda_l1=205.6999,
        lambda_l2=580.9768,
        max_depth=8,
        num_leaves=210,
        num_threads=20
    )

    with R.start(experiment_name="test"):
        model.fit(dataset)

        R.save_objects(trained_model=model)

        recorder = R.get_recorder()
        print(f"实验ID: {recorder.id}")

    predictions = model.predict(dataset=dataset)

    print(predictions.head())