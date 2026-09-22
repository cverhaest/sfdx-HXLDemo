/**
 * Data container that defines the payload shape for the AccountSummary
 * Custom Lightning Type. Its @AuraEnabled fields are the source of truth for
 * the type's schema and for the HXL widget that renders it.
 */
public class AccountSummary {
    /**
     * The name of the account, displayed as the card header.
     */
    @AuraEnabled
    public String accountName { get; set; }

    /**
     * A generated summary of the account, displayed in the card body.
     */
    @AuraEnabled
    public String summary { get; set; }
}
