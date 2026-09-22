/**
 * Agentforce (invocable) action that generates a natural-language summary of an
 * Account by invoking the "Account Record Summary" prompt template, and returns
 * the result as an {@link AccountSummary} payload — the Apex type that backs the
 * AccountSummary Custom Lightning Type.
 */
public with sharing class AccountSummaryAction {
    /**
     * Developer name of the prompt template invoked by this action.
     */
    @TestVisible
    private static final String PROMPT_TEMPLATE_DEV_NAME = 'Account_Record_Summary_Prompt_Templace';

    /**
     * Reference name of the template's SObject input parameter (see the
     * template's <inputs><referenceName> definition).
     */
    @TestVisible
    private static final String INPUT_PARAM_ACCOUNT = 'Input:Account';

    /**
     * Input for the invocable action: the Account to summarize.
     */
    public class Request {
        @InvocableVariable(
            label='Account ID'
            description='Id of the Account to summarize.'
            required=true
        )
        public Id accountId;
    }

    /**
     * Output of the invocable action: the generated Account summary payload,
     * mapped to the AccountSummary Custom Lightning Type by Agentforce.
     */
    public class Response {
        @InvocableVariable(
            label='Account Summary'
            description='Generated account summary (account name + summary text).'
        )
        public AccountSummary accountSummary;
    }

    /**
     * Domain exception for account-summary generation failures.
     */
    public class AccountSummaryActionException extends Exception {}

    /**
     * Generates an Account summary for each request by calling the
     * "Account Record Summary" prompt template.
     *
     * @param requests One request per Account to summarize.
     * @return One response per request, in the same order, each carrying an
     *         {@link AccountSummary} payload.
     * @example
     * AccountSummaryAction.Request req = new AccountSummaryAction.Request();
     * req.accountId = someAccountId;
     * List<AccountSummaryAction.Response> out =
     *     AccountSummaryAction.summarizeAccounts(new List<AccountSummaryAction.Request>{ req });
     */
    @InvocableMethod(
        label='Summarize Account Record'
        description='Summarizes an Account using the Account Record Summary prompt template and returns an AccountSummary.'
        category='Agentforce'
    )
    public static List<Response> summarizeAccounts(List<Request> requests) {
        List<Response> responses = new List<Response>();
        if (requests == null || requests.isEmpty()) {
            return responses;
        }

        // Collect ids once, then resolve names in a single bulk query.
        Set<Id> accountIds = new Set<Id>();
        for (Request req : requests) {
            if (req != null && req.accountId != null) {
                accountIds.add(req.accountId);
            }
        }

        Map<Id, Account> accountsById = new Map<Id, Account>(
            [SELECT Id, Name FROM Account WHERE Id IN :accountIds WITH USER_MODE]
        );

        for (Request req : requests) {
            responses.add(buildResponse(req, accountsById));
        }

        return responses;
    }

    /**
     * Builds a single response, generating the summary only when the request
     * references a resolvable Account.
     *
     * @param req The request to process.
     * @param accountsById Accounts resolved for this invocation, keyed by Id.
     * @return A response carrying an {@link AccountSummary} payload (empty when
     *         the request Account cannot be resolved).
     */
    private static Response buildResponse(Request req, Map<Id, Account> accountsById) {
        Response res = new Response();
        AccountSummary summary = new AccountSummary();

        Account acc = (req?.accountId != null) ? accountsById.get(req.accountId) : null;
        if (acc != null) {
            summary.accountName = acc.Name;
            summary.summary = generateSummary(req.accountId);
        }

        res.accountSummary = summary;
        return res;
    }

    /**
     * Invokes the prompt template for a single Account and returns the generated
     * text.
     *
     * @param accountId Id of the Account to summarize.
     * @return The generated summary text, or null when the model returns no
     *         generation.
     * @throws AccountSummaryActionException When the prompt template invocation
     *         fails.
     */
    private static String generateSummary(Id accountId) {
        try {
            ConnectApi.EinsteinPromptTemplateGenerationsInput input =
                new ConnectApi.EinsteinPromptTemplateGenerationsInput();

            // The template's Account input is an SObject reference; pass the record id.
            ConnectApi.WrappedValue accountValue = new ConnectApi.WrappedValue();
            accountValue.value = new Map<String, Object>{ 'id' => accountId };

            input.inputParams = new Map<String, ConnectApi.WrappedValue>{
                INPUT_PARAM_ACCOUNT => accountValue
            };

            input.additionalConfig = new ConnectApi.EinsteinLlmAdditionalConfigInput();
            input.additionalConfig.applicationName = 'PromptBuilderPreview';
            input.isPreview = false;

            ConnectApi.EinsteinPromptTemplateGenerationsRepresentation output =
                ConnectApi.EinsteinLLM.generateMessagesForPromptTemplate(
                    PROMPT_TEMPLATE_DEV_NAME,
                    input
                );

            if (output?.generations != null && !output.generations.isEmpty()) {
                return output.generations[0].text;
            }
            return null;
        } catch (Exception e) {
            throw new AccountSummaryActionException(
                'Failed to generate account summary for ' + accountId + ': ' + e.getMessage(),
                e
            );
        }
    }
}
