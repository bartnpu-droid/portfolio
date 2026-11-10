<?php
/**
 * Title: Checkout header
 * Slug: ombra/checkout-header
 * Categories: header
 * Block Types: core/template-part/checkout-header
 * Inserter: no
 *
 * A quiet header for the checkout: back to the bag, the wordmark, a secure-checkout note.
 *
 * @package Ombra
 */

$ombra_cart_url = function_exists( 'wc_get_cart_url' ) ? wc_get_cart_url() : home_url( '/' );
?>
<!-- wp:group {"className":"ombra-header ombra-header--checkout","style":{"spacing":{"padding":{"top":"1.2rem","bottom":"1.2rem"}},"border":{"bottom":{"color":"var:preset|color|line","width":"1px"}}},"layout":{"type":"constrained"}} -->
<div class="wp-block-group ombra-header ombra-header--checkout" style="border-bottom-color:var(--wp--preset--color--line);border-bottom-width:1px;padding-top:1.2rem;padding-bottom:1.2rem">
<!-- wp:group {"align":"wide","className":"ombra-header__row","layout":{"type":"flex","flexWrap":"nowrap","justifyContent":"space-between"}} -->
<div class="wp-block-group alignwide ombra-header__row">
<!-- wp:paragraph {"className":"ombra-back-link","fontSize":"small"} -->
<p class="ombra-back-link has-small-font-size"><a href="<?php echo esc_url( $ombra_cart_url ); ?>"><?php esc_html_e( '← Back to bag', 'ombra' ); ?></a></p>
<!-- /wp:paragraph -->

<!-- wp:site-title {"level":0,"textAlign":"center","className":"ombra-wordmark"} /-->

<!-- wp:paragraph {"align":"right","className":"ombra-secure","fontSize":"small"} -->
<p class="has-text-align-right ombra-secure has-small-font-size"><?php esc_html_e( 'Secure checkout', 'ombra' ); ?></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->
</div>
<!-- /wp:group -->
