package example;

public enum PageType {
    HOMEPAGE_COLUMN_FEED(14),
    LEGACY_HOME_PANEL(17);

    private final int code;

    PageType(int code) {
        this.code = code;
    }

    public int getCode() {
        return code;
    }
}
