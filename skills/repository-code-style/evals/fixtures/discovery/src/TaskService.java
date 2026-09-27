package example;

import java.util.LinkedHashMap;
import java.util.Map;

public class TaskService {
    public boolean legacyHasValue(String value) {
        return value != null;
    }

    public boolean shouldHandle(String value) {
        throw new UnsupportedOperationException("pending");
    }

    public int pageType() {
        return 17;
    }

    public Map<String, Object> response(int count, long lastNumber) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("count", count);
        result.put("lastNumber", lastNumber);
        return result;
    }
}
