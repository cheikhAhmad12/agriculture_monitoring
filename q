import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt

# Load datasets
train_file_path = 'train_FD001.txt'
test_file_path = 'test_FD001.txt'

df_train = pd.read_csv(train_file_path, delim_whitespace=True, header=None)
df_test = pd.read_csv(test_file_path, delim_whitespace=True, header=None)

# Define column names (based on C-MAPSS dataset structure)
column_names = ['unit', 'cycle', 'operational_setting_1', 'operational_setting_2',
                'operational_setting_3', 'sensor_1', 'sensor_2', 'sensor_3', 'sensor_4',
                'sensor_5', 'sensor_6', 'sensor_7', 'sensor_8', 'sensor_9', 'sensor_10',
                'sensor_11', 'sensor_12', 'sensor_13', 'sensor_14', 'sensor_15',
                'sensor_16', 'sensor_17', 'sensor_18', 'sensor_19', 'sensor_20', 'sensor_21']
df_train.columns = column_names
df_test.columns = column_names

# Compute RUL (Remaining Useful Life) for training data
rul_df = df_train.groupby('unit')['cycle'].max().reset_index()
rul_df.columns = ['unit', 'max_cycle']
df_train = df_train.merge(rul_df, on='unit')
df_train['RUL'] = df_train['max_cycle'] - df_train['cycle']
df_train.drop(columns=['max_cycle'], inplace=True)

# Normalize sensor data
scaler = MinMaxScaler()
sensor_columns = column_names[2:]
df_train[sensor_columns] = scaler.fit_transform(df_train[sensor_columns])
df_test[sensor_columns] = scaler.transform(df_test[sensor_columns])

# Create sequences for LSTM input
def create_sequences(data, seq_length=50):
    sequences, labels = [], []
    for unit in data['unit'].unique():
        unit_data = data[data['unit'] == unit]
        for i in range(len(unit_data) - seq_length):
            seq = unit_data.iloc[i:i+seq_length][sensor_columns].values
            label = unit_data.iloc[i+seq_length]['RUL'] if 'RUL' in unit_data.columns else None
            sequences.append(seq)
            labels.append(label)
    return np.array(sequences), np.array(labels) if labels[0] is not None else None

sequence_length = 50
X_train, y_train = create_sequences(df_train, seq_length=sequence_length)
X_test, _ = create_sequences(df_test, seq_length=sequence_length)

X_train = np.reshape(X_train, (X_train.shape[0], X_train.shape[1], X_train.shape[2]))
X_test = np.reshape(X_test, (X_test.shape[0], X_test.shape[1], X_test.shape[2]))

# Define LSTM model
model = Sequential([
    LSTM(100, return_sequences=True, input_shape=(sequence_length, len(sensor_columns))),
    Dropout(0.2),
    LSTM(50, return_sequences=False),
    Dropout(0.2),
    Dense(25, activation='relu'),
    Dense(1)
])

model.compile(optimizer='adam', loss='mse', metrics=['mae'])

# Train model
epochs = 20
batch_size = 64
model.fit(X_train, y_train, epochs=epochs, batch_size=batch_size, validation_split=0.2)

# Evaluate and predict
y_pred = model.predict(X_test)
plt.figure(figsize=(10,5))
plt.plot(y_pred, label='Predicted RUL')
plt.legend()
plt.show()

# Save the model
model.save('/mnt/data/lstm_rul_model.h5')

