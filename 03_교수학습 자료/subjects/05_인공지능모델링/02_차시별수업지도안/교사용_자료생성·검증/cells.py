import traceback,io,contextlib,sys
CELLS=[
("L1a","import pandas as pd; df = pd.read_csv('drive_log.csv'); print(df.head())"),
("L1b","print(len(df), df['run'].nunique())"),
("L1c","print(df['label'].value_counts())"),
("L3a","print(df.groupby('run')['bright'].mean().round())"),
("L4a","print(df[df['run'] == 3].iloc[20:25])"),
("L4b","from sklearn.model_selection import train_test_split; train, val = train_test_split(df, test_size=0.2, random_state=42); print(len(train), len(val))"),
("L4c","print(sorted(set(train['run']) & set(val['run'])))"),
("L4d","print(sorted(val[val['run'] == 3]['frame'])[:6]); print(sorted(train[train['run'] == 3]['frame'])[:6])"),
("L4e","train2 = df[df['run'] <= 8]; val2 = df[df['run'] >= 9]; print(len(train2), len(val2), sorted(set(train2['run']) & set(val2['run'])))"),
("L4err1","print(df['Run'].nunique())"),
("L4err2","train, val = train_test_split(df, test_size=20, random_state=42); print(len(val))"),
("L4f","print(val['run'].value_counts().sort_index().to_dict())"),
("L5a","import pandas as pd; from sklearn.model_selection import train_test_split; from sklearn.neighbors import KNeighborsClassifier; df = pd.read_csv('drive_log.csv'); cols = ['line_near', 'line_far', 'bright']"),
("L5b","train, val = train_test_split(df, test_size=0.2, random_state=42); m1 = KNeighborsClassifier(n_neighbors=3).fit(train[cols], train['label']); print(round(m1.score(val[cols], val['label']), 3))"),
("L5c","train2 = df[df['run'] <= 8]; val2 = df[df['run'] >= 9]; m2 = KNeighborsClassifier(n_neighbors=3).fit(train2[cols], train2['label']); print(round(m2.score(val2[cols], val2['label']), 3))"),
("L5d","print(pd.crosstab(val2['label'], m2.predict(val2[cols]), rownames=['정답'], colnames=['예측']))"),
("L5e","print(round(m2.score(train2[cols], train2['label']), 3))"),
("L5err1","m3 = KNeighborsClassifier(n_neighbors=3).fit(df[cols], df['label']); print(round(m3.score(val2[cols], val2['label']), 3))"),
("L5err2","KNeighborsClassifier(n_neighbors=3).fit(df, df['label'])"),
("L5f","print(val2['label'].value_counts())"),
("L6a","import numpy as np; import pandas as pd; d = np.load('train_frames.npz'); c = np.load('car_frames.npz'); print(d['X'].shape, c['X'].shape)"),
("L6b","print(d['X'].dtype, d['X'].min(), d['X'].max()); print(c['X'].dtype, c['X'].min(), c['X'].max())"),
("L6c","print(d['y'][0], d['X'][0, 23, 12:20, :].tolist())"),
("L6d","print(c['y'][0], c['X'][0, 47, 26:36, :].tolist())"),
("L6e","from sklearn.neighbors import KNeighborsClassifier; from sklearn.model_selection import train_test_split; X = (d['X'] / 255).reshape(300, -1); Xtr, Xva, ytr, yva = train_test_split(X, d['y'], test_size=0.2, random_state=42); m = KNeighborsClassifier(n_neighbors=5).fit(Xtr, ytr); print(round(m.score(Xva, yva), 3))"),
("L6err1","m.predict(c['X'].reshape(60, -1))"),
("L6f","small = c['X'][:, ::2, ::2]; print(small.shape); print(round(m.score(small.reshape(60, -1), c['y']), 3))"),
("L6g","print(pd.Series(m.predict(small.reshape(60, -1))).value_counts()); print(pd.Series(c['y']).value_counts())"),
("L7setup","import numpy as np; import pandas as pd; from sklearn.neighbors import KNeighborsClassifier; from sklearn.model_selection import train_test_split; d = np.load('train_frames.npz'); c = np.load('car_frames.npz'); X = (d['X'] / 255).reshape(300, -1); Xtr, Xva, ytr, yva = train_test_split(X, d['y'], test_size=0.2, random_state=42); m = KNeighborsClassifier(n_neighbors=5).fit(Xtr, ytr); small = c['X'][:, ::2, ::2]; print(round(m.score(Xva, yva), 3), small.shape)"),
("L7a","print(round(m.score((small / 255).reshape(60, -1), c['y']), 3))"),
("L7b","print(round(m.score(small[..., ::-1].reshape(60, -1), c['y']), 3))"),
("L7c","def prep(img): return (img[:, ::2, ::2, ::-1] / 255).reshape(len(img), -1)"),
("L7d","print(round(m.score(prep(c['X']), c['y']), 3))"),
("L7err1","print(round(m.score(prep(c['X']) / 255, c['y']), 3))"),
("L7e","print(round(prep(c['X']).min(), 2), round(prep(c['X']).max(), 2), round(X.min(), 2), round(X.max(), 2))"),
("L7f","print(pd.crosstab(c['y'], m.predict(prep(c['X'])), rownames=['정답'], colnames=['예측']))"),
]
g={}
import pandas as pd
pd.set_option('display.width',120)
for k,src in CELLS:
    f=io.StringIO()
    with contextlib.redirect_stdout(f):
        try: exec(src,g)
        except Exception as e:
            print(f"{type(e).__name__}: {e}")
    print(f"### {k}\n>>> {src}\n{f.getvalue()}")
