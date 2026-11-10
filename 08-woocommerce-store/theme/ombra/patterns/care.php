<?php
/**
 * Title: Candle care tips
 * Slug: ombra/care
 * Categories: ombra
 * Keywords: care, tips, how to
 * Viewport width: 1400
 *
 * @package Ombra
 */

$ombra_tips = array(
	array( '01', __( 'First burn: two hours', 'ombra' ), __( 'Let the wax melt to the edge of the jar the first time, so it does not tunnel.', 'ombra' ) ),
	array( '02', __( 'Trim the wick to 5 mm', 'ombra' ), __( 'Before every burn. A short wick gives a calm flame and a clean jar.', 'ombra' ) ),
	array( '03', __( 'Four hours at most', 'ombra' ), __( 'Then put it out with the lid or a snuffer, never with water.', 'ombra' ) ),
);
?>
<!-- wp:group {"className":"ombra-section ombra-care","style":{"spacing":{"padding":{"top":"var:preset|spacing|60","bottom":"var:preset|spacing|60"},"blockGap":"var:preset|spacing|50"}},"layout":{"type":"constrained"}} -->
<div class="wp-block-group ombra-section ombra-care" style="padding-top:var(--wp--preset--spacing--60);padding-bottom:var(--wp--preset--spacing--60)">
<!-- wp:group {"align":"wide","className":"ombra-section__head","layout":{"type":"flex","flexWrap":"wrap","justifyContent":"space-between","verticalAlignment":"bottom"}} -->
<div class="wp-block-group alignwide ombra-section__head">
<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading"><?php esc_html_e( 'Burn it right', 'ombra' ); ?></h2>
<!-- /wp:heading -->

<!-- wp:paragraph {"className":"ombra-link-arrow"} -->
<p class="ombra-link-arrow"><a href="<?php echo esc_url( ombra_page_url( 'candle-care' ) ); ?>"><?php esc_html_e( 'The full candle care guide', 'ombra' ); ?></a></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->

<!-- wp:columns {"align":"wide","style":{"spacing":{"blockGap":{"left":"var:preset|spacing|40","top":"var:preset|spacing|40"}}}} -->
<div class="wp-block-columns alignwide">
<?php foreach ( $ombra_tips as $ombra_tip ) : ?>
<!-- wp:column {"className":"ombra-tip"} -->
<div class="wp-block-column ombra-tip">
<!-- wp:paragraph {"className":"ombra-tip__number","textColor":"accent","fontSize":"x-large","fontFamily":"fraunces"} -->
<p class="ombra-tip__number has-accent-color has-text-color has-fraunces-font-family has-x-large-font-size"><?php echo esc_html( $ombra_tip[0] ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3,"fontSize":"large"} -->
<h3 class="wp-block-heading has-large-font-size"><?php echo esc_html( $ombra_tip[1] ); ?></h3>
<!-- /wp:heading -->

<!-- wp:paragraph {"textColor":"contrast-2"} -->
<p class="has-contrast-2-color has-text-color"><?php echo esc_html( $ombra_tip[2] ); ?></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:column -->
<?php endforeach; ?>
</div>
<!-- /wp:columns -->
</div>
<!-- /wp:group -->
