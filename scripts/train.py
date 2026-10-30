"""Train the calibrated model from cleaned historical orders."""
import pandas as pd
from engine.cleaning import clean_orders, training_rows
from engine.model import train_model

def main() -> None:
    """Clean, train, and print model metrics."""
    metrics=train_model(training_rows(clean_orders(pd.read_csv("orders_sample.csv"))))
    print(metrics)

if __name__=="__main__": main()
