import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model
from sklearn.preprocessing import MinMaxScaler

def predict_engine(unit_id, file_path, model_path='lstm_classification_model.h5', seq_length=50):

    df = pd.read_csv(file_path, delim_whitespace=True, header=None)
    column_names = ['unit', 'cycle', 'operational_setting_1', 'operational_setting_2',
                    'operational_setting_3', 'sensor_1', 'sensor_2', 'sensor_3', 'sensor_4',
                    'sensor_5', 'sensor_6', 'sensor_7', 'sensor_8', 'sensor_9', 'sensor_10',
                    'sensor_11', 'sensor_12', 'sensor_13', 'sensor_14', 'sensor_15',
                    'sensor_16', 'sensor_17', 'sensor_18', 'sensor_19', 'sensor_20', 'sensor_21']
    df.columns = column_names
    sensor_columns = column_names[2:]
    scaler = MinMaxScaler()
    df[sensor_columns] = scaler.fit_transform(df[sensor_columns])
    
    unit_data = df[df['unit'] == unit_id]
    unit_data_values = unit_data[sensor_columns].values
    if len(unit_data_values) < seq_length:
        pad = np.zeros((seq_length - len(unit_data_values), len(sensor_columns)))
        unit_data_values = np.vstack((pad, unit_data_values))
    else:
        unit_data_values = unit_data_values[-seq_length:]
    
    unit_data_values = np.array([unit_data_values])
    model = load_model(model_path)
    
    # Predict probability of faillure
    prob = model.predict(unit_data_values)[0][0]
    pred_class = int(prob > 0.5)
    print(f"Engine {unit_id} - Predicted Probability of Failure: {prob:.4f}")
    print(f"Engine {unit_id} - Predicted Class: {pred_class} (0 = Healthy, 1 = At Risk)")
    
    return prob, pred_class