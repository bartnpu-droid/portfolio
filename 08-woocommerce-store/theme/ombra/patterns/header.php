<?php
/**
 * Title: Header
 * Slug: ombra/header
 * Categories: header
 * Block Types: core/template-part/header
 * Inserter: no
 *
 * Announcement bar (live free shipping message from the Ombra Store Tools plugin),
 * then menu, wordmark, search, account and the mini-cart drawer.
 *
 * @package Ombra
 */

?>
<!-- wp:group {"className":"ombra-announcement","style":{"spacing":{"padding":{"top":"0.6rem","bottom":"0.6rem"}}},"backgroundColor":"contrast","textColor":"base","fontSize":"x-small","layout":{"type":"constrained"}} -->
<div class="wp-block-group ombra-announcement has-base-color has-contrast-background-color has-text-color has-background has-x-small-font-size" style="padding-top:0.6rem;padding-bottom:0.6rem">
<!-- wp:ombra/free-shipping-progress {"variant":"text"} /-->

<!-- wp:paragraph {"align":"center","className":"ombra-announcement__fallback"} -->
<p class="has-text-align-center ombra-announcement__fallback"><?php esc_html_e( 'Hand-poured in small batches', 'ombra' ); ?></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->

<!-- wp:group {"className":"ombra-header","style":{"spacing":{"padding":{"top":"1rem","bottom":"1rem"}},"border":{"bottom":{"color":"var:preset|color|line","width":"1px"}}},"layout":{"type":"constrained"}} -->
<div class="wp-block-group ombra-header" style="border-bottom-color:var(--wp--preset--color--line);border-bottom-width:1px;padding-top:1rem;padding-bottom:1rem">
<!-- wp:group {"align":"wide","className":"ombra-header__row","layout":{"type":"flex","flexWrap":"nowrap","justifyContent":"space-between"}} -->
<div class="wp-block-group alignwide ombra-header__row">
<!-- wp:navigation {"overlayMenu":"mobile","className":"ombra-nav","layout":{"type":"flex","justifyContent":"left"}} -->
<!-- wp:navigation-link {"label":"<?php esc_attr_e( 'Shop all', 'ombra' ); ?>","url":"<?php echo esc_url_raw( ombra_shop_url() ); ?>","kind":"custom","isTopLevelLink":true} /-->
<!-- wp:navigation-link {"label":"<?php esc_attr_e( 'Candles', 'ombra' ); ?>","url":"<?php echo esc_url_raw( ombra_category_url( 'candles' ) ); ?>","kind":"custom","isTopLevelLink":true} /-->
<!-- wp:navigation-link {"label":"<?php esc_attr_e( 'Diffusers + sprays', 'ombra' ); ?>","url":"<?php echo esc_url_raw( ombra_category_url( 'diffusers-sprays' ) ); ?>","kind":"custom","isTopLevelLink":true} /-->
<!-- wp:navigation-link {"label":"<?php esc_attr_e( 'Gift sets', 'ombra' ); ?>","url":"<?php echo esc_url_raw( ombra_category_url( 'gift-sets' ) ); ?>","kind":"custom","isTopLevelLink":true} /-->
<!-- wp:navigation-link {"label":"<?php esc_attr_e( 'Candle care', 'ombra' ); ?>","url":"<?php echo esc_url_raw( ombra_page_url( 'candle-care' ) ); ?>","kind":"custom","isTopLevelLink":true} /-->
<!-- /wp:navigation -->

<!-- wp:site-title {"level":0,"textAlign":"center","className":"ombra-wordmark"} /-->

<!-- wp:group {"className":"ombra-header__actions","style":{"spacing":{"blockGap":"0.4rem"}},"layout":{"type":"flex","flexWrap":"nowrap","justifyContent":"right"}} -->
<div class="wp-block-group ombra-header__actions">
<!-- wp:search {"label":"<?php esc_attr_e( 'Search the shop', 'ombra' ); ?>","showLabel":false,"placeholder":"<?php esc_attr_e( 'Search candles and scents', 'ombra' ); ?>","buttonText":"<?php esc_attr_e( 'Search', 'ombra' ); ?>","buttonPosition":"button-only","buttonUseIcon":true,"isSearchFieldHidden":true,"query":{"post_type":"product"},"className":"ombra-search"} /-->

<!-- wp:woocommerce/customer-account {"displayStyle":"icon_only","iconStyle":"line","iconClass":"wc-block-customer-account__account-icon","className":"ombra-account"} /-->

<!-- wp:woocommerce/mini-cart {"miniCartIcon":"bag","addToCartBehaviour":"open_drawer","hasHiddenPrice":true,"className":"ombra-bag"} /-->
</div>
<!-- /wp:group -->
</div>
<!-- /wp:group -->
</div>
<!-- /wp:group -->
