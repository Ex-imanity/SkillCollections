# Frontend repository scenarios

Synthetic, self-contained excerpts; these are not Gaotu source or real API services.
Return implementation sketches and evidence/verification notes. Do not modify a
business repository, add dependencies, or claim a build/browser check ran.

## S7: C-end H5 response boundary and product scope

Task: Add a method that loads product cards to the existing Vue Options API page.
The API returns the envelope below. A valid product code and count can both be 0.
Preserve the user's selected product code, keep identifiers as strings, and use
the page's existing request entry point. Do not move a product-only method to the
multi-product base layer.

`fixture/h5/packages/alpha/pages/Products.vue` currently declares:

```javascript
export default {
    data() {
        return { productCode: 0, cards: [], total: 0, loading: false };
    },
    methods: {
        async loadSummary() {
            const response = await this.$api.alphaApi.getSummary({
                productCode: this.productCode,
            });
            if (response.code === 0) {
                this.total = response.data.total;
            }
        },
    },
};
```

`fixture/h5/business/api/alphaApi.js` uses the current H5 wrapper:

```javascript
export default (axios) => ({
    getSummary: (params) => axios.get('/alpha/summary', { params }),
    getCards: (params) => axios.get('/alpha/cards', { params }),
});
```

`fixture/h5/base/plugins/axios-contract.md`: the supplied axios wrapper already
removes the HTTP transport envelope; API methods resolve to the BUSINESS envelope,
not to its inner data. They reject on transport failure. No browser-only global is
needed to call these methods. API data shape:

```json
{"code":0,"data":{"cards":[{"id":"9007199254740993"}],"total":0}}
```

`fixture/h5/packages/alpha/.editorconfig`: four spaces and LF. The legacy sister
product uses tabs and a different API/plugin registration. That sister product is
not being changed. No frontend TypeScript migration or React component was requested.

## S8: B-end table request mapping and stable false/zero values

Task: Add a table request method within the admin page's existing model module.
Keep current pagination, status filters and the established service/model split.

`fixture/admin/services/cards.ts`:

```typescript
export function listCards(params: CardListRequest) {
    return baseRequest.post('/card/list', params);
}
```

`fixture/admin/interfaces/cards.ts`:

```typescript
export interface CardListRequest {
    pageIndex: number;
    pageSize: number;
    status?: number;
    published?: boolean;
}
export interface CardListData {
    list: Array<{ id: string }>;
    total: number;
}
```

`fixture/admin/services/base-contract.md`: baseRequest resolves directly to
CardListData, rejects on failure, and owns auth and service-prefix behavior. The
existing sibling model passes UI current to API pageIndex. Table request results
are `{ data: list, total, success: true }`; do not return an H5 business envelope.

`fixture/admin/models/cards.ts` has a pending method accepting:

```typescript
type TableInput = {
    current: number;
    pageSize: number;
    status?: number;
    published?: boolean;
};
```

A representative input is `{ current: 2, pageSize: 20, status: 0, published: false }`.
The repository already keeps loading/error state in its request model; do not add
a second request-state framework or change where error handling belongs.

## S9: Display fallback vs submission protocol and tracked formatting

Task: Display a fallback for a missing cover URL in an H5 item. Keep the original
stored URL unchanged, because the update API requires an empty string to clear it.

`fixture/h5/packages/alpha/pages/CoverEditor.vue`:

```javascript
export default {
    data() {
        return { coverUrl: '', fallbackCover: 'asset-cover-placeholder.png' };
    },
    methods: {
        save() {
            return this.$api.alphaApi.updateCover({ coverUrl: this.coverUrl });
        },
    },
};
```

The image currently binds to coverUrl directly. Neighboring product examples use
a display-only computed value for fallback, and preserve the original form value
on submit. One old example mutates coverUrl to the placeholder URL in mounted;
that behavior violates this task's clear-value protocol. The current product's
tracked .editorconfig says four spaces/LF; an older author patch uses tabs.

## Evaluation request

For S7-S9, return the concrete sketch, the local evidence selected, conflicts
resolved, and the smallest useful verification. Keep protocol fields and raw
form values intact; do not assert company-wide frontend rules from this fixture.
