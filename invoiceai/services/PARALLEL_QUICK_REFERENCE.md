# Parallel Processing Quick Reference

## 🚀 One-Liner Usage

```python
from odoo.addons.purpleai.invoiceai.services.document_processing_service import process_documents_parallel

result = process_documents_parallel(self.env, client, [
    ('/path/invoice1.pdf', 'invoice1.pdf', None),
    ('/path/invoice2.pdf', 'invoice2.pdf', None),
], max_workers=2)
```

## 📊 Performance Comparison

| Workers | Time for 10 Files | Speed | Quality | Tokens per Invoice | Recommendation |
|---------|-------------------|-------|---------|-------------------|-----------------|
| 1 | ~300 sec | 2 files/min | **High** | 800-1200 | Debugging only |
| **2** | ~150 sec | 4 files/min | **High** | 800-1200 | ✅ **Recommended** |
| 3 | ~100 sec | 6 files/min | **Medium** | 800-1200 | Good internet needed |
| 4 | ~75 sec | 8 files/min | **Low** | 800-1200 | ⚠️ Rate limit risk |

## ⚙️ Configuration (Odoo Settings)

**Key:** `ai_core.max_parallel_workers`  
**Values:** 1, 2, 3, or 4  
**Default:** 2 (safe)

## 📋 Return Value

```python
{
    'success_count': 3,         # ✅ Extracted
    'fail_count': 0,            # ❌ Failed
    'total': 3,                 # Total processed
    'duration_sec': 45.23,      # Elapsed time
    'speed': 4.0,               # Files/minute
    'completed': [...],         # Successful records
    'failed': [...]             # Failed files list
}
```

## 🔧 Function Signature

```python
process_documents_parallel(
    env,              # Odoo environment (self.env)
    client,           # purple_ai.client_master record
    file_list,        # [(path, name, record), ...]
    max_workers=None  # Auto-uses config or defaults to 2
)
```

## 📝 Examples by Use Case

### Sequential Processing (DEBUG)
```python
result = process_documents_parallel(env, client, file_list, max_workers=1)
```

### Normal Batch (4x faster, safe)
```python
result = process_documents_parallel(env, client, file_list, max_workers=2)
```

### High-Volume (9x faster, requires good internet)
```python
result = process_documents_parallel(env, client, file_list, max_workers=3)
```

### Use Default Config
```python
result = process_documents_parallel(env, client, file_list)  # Uses system setting
```

## 🎯 When to Use Each

| Scenario | Workers | Quality | Tokens/Invoice | Reason |
|----------|---------|---------|-----------------|--------|
| Development | 1 | **High** | 800-1200 | Sequential debugging |
| Normal import | 2 | **High** | 800-1200 | 4x speed, safe |
| Bulk upload | 3 | **Medium** | 800-1200 | 9x speed, stable internet only |
| Enterprise | 4 | **Low** | 800-1200 | Maximum throughput (monitor rate limits) |

## ✅ Logging Output

```
🚀 PARALLEL BATCH PROCESSING STARTED
📁 Files to process: 3
⚙️  Thread workers: 2

  ⏳ Processing: invoice1.pdf [Thread]
Progress: 1/3 (33%)
  ✅ Completed: invoice1.pdf

🏁 PARALLEL BATCH PROCESSING COMPLETE
✅ Successful: 3 files
⚡ Speed: 4.0 files/minute
```

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Rate limited | Reduce workers to 2 |
| Memory high | Reduce workers or batch size |
| Timeout errors | Check network, may need more time |
| Silent failures | Enable `purple_ai.detailed_logging = True` |
| Some files fail | Check `result['failed']` list |

## 📦 File List Format

```python
file_list = [
    (file_path, filename, existing_record_or_none),
    ('/tmp/inv1.pdf', 'invoice1.pdf', None),
    ('/tmp/inv2.pdf', 'invoice2.pdf', extraction_record),
]
```

## 💾 Example Integration

```python
# In a model/service method
def batch_import(self, pdf_paths):
    file_list = [(p, Path(p).name, None) for p in pdf_paths]
    result = process_documents_parallel(
        self.env, 
        self.client_id,  # purple_ai.client_master
        file_list,
        max_workers=2
    )
    
    print(f"✅ {result['success_count']} extracted in {result['duration_sec']:.1f}s")
    print(f"❌ {result['fail_count']} failed")
    
    return result['completed']
```

## 🔐 Safety Limits

- Auto-clamps workers to 1-4
- 600s timeout per file (configurable)
- Thread-safe in Odoo
- Error handling per thread (one failure doesn't crash pool)

---

**For detailed guide:** See `PARALLEL_PROCESSING_GUIDE.md`
